"""Orchestrateur Étage 3 — enrichissement L2 → L3.

Logique :
1. Pour chaque LeadStage2 :
   a. Si chaîne → on saute, source="chaine_non_traitee"
   b. Sinon, scraping mentions légales du site_web
   c. Génération patterns (nominatifs si dirigeant L2 trouvé + fonctionnels génériques)
   d. Construction LeadStage3
2. Sauvegarde incrémentale tous les 20 leads (callback)
3. Cache via SessionCache (URLs scrapées)
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ..common.cache import SessionCache
from ..common.logger import get_logger
from ..models import LeadStage2, LeadStage3
from .pattern_generator import generer_tous_patterns
from .scraper import (
    RESEAU_BLOQUE,
    ResultatScraping,
    ScraperContact,
    apparier_linkedin,
    extraire_domaine,
)

logger = get_logger(__name__)


class EnricheurStage3:
    """Pipeline L2 → L3 : scraping + patterns."""

    def __init__(
        self,
        scraper: ScraperContact,
        cache: SessionCache | None = None,
        callback_save_incremental=None,
        max_workers: int = 1,
    ):
        self.scraper = scraper
        self.cache = cache
        self.callback_save = callback_save_incremental
        self.max_workers = max(1, int(max_workers))
        self._reseau_bloque_signale = False

    def _scraper_avec_cache(self, site_web: str | None) -> ResultatScraping:
        """Scrape avec cache (évite re-scraping en cas de relance)."""
        if not site_web:
            return ResultatScraping(raison_echec="pas_de_site_web")

        cache_key = f"scraping:{site_web.lower()}"
        if self.cache:
            cached = self.cache.get_place(place_id=cache_key, stage="stage3_scrape")
            if cached is not None:
                return ResultatScraping(
                    domaine=cached.get("domaine"),
                    emails=cached.get("emails", []) or [],
                    page_source=cached.get("page_source"),
                    raison_echec=cached.get("raison_echec"),
                    pages_visitees=cached.get("pages_visitees", []) or [],
                    signaux_ve=cached.get("signaux_ve", []) or [],
                    linkedins=cached.get("linkedins", []) or [],
                )

        try:
            result = self.scraper.scraper(site_web)
        except Exception as e:  # noqa: BLE001
            logger.warning("Scraping échec dur pour %s : %s", site_web, e)
            result = ResultatScraping(raison_echec=f"erreur_scraping: {type(e).__name__}")

        if self.cache:
            self.cache.store_place(
                place_id=cache_key,
                stage="stage3_scrape",
                payload={
                    "domaine": result.domaine,
                    "emails": list(result.emails),
                    "page_source": result.page_source,
                    "raison_echec": result.raison_echec,
                    "pages_visitees": list(result.pages_visitees),
                    "signaux_ve": list(result.signaux_ve),
                    "linkedins": list(result.linkedins),
                },
            )
        return result

    def _enrichir_un_lead(self, lead: LeadStage2) -> LeadStage3:
        """Enrichit un L2 → L3."""
        # Si chaîne → on ne génère ni scraping ni patterns nominatifs
        if lead.flag_chaine:
            return LeadStage3(
                **lead.model_dump(),
                emails_verifies=[],
                emails_candidats=[],
                source_globale="chaine_non_traitee",
                contient_dirigeant_pattern=False,
                nb_emails_verifies=0,
                nb_emails_candidats=0,
            )

        # Étape 1 — Scraping
        site_web = lead.site_web
        domaine_extrait: str | None = None
        emails_scrapes: list[str] = []
        page_source: str | None = None
        signaux_ve: list[str] = []
        linkedin_dirigeant_site: str | None = None
        linkedin_entreprise_site: str | None = None

        if site_web:
            scraping = self._scraper_avec_cache(site_web)
            domaine_extrait = scraping.domaine
            emails_scrapes = scraping.emails
            page_source = scraping.page_source
            signaux_ve = scraping.signaux_ve
            linkedin_dirigeant_site, linkedin_entreprise_site = apparier_linkedin(
                scraping.linkedins, lead.dirigeant_prenom, lead.dirigeant_nom
            )

            if scraping.raison_echec == RESEAU_BLOQUE and not self._reseau_bloque_signale:
                logger.warning(
                    "Scraping L3 de fait désactivé par la politique réseau "
                    "(allowlist) — les emails ne pourront pas être collectés "
                    "dans cet environnement."
                )
                self._reseau_bloque_signale = True

        # Si pas de domaine via scraping, on tente l'extraction directe
        if domaine_extrait is None and site_web:
            domaine_extrait = extraire_domaine(site_web)

        # Étape 2 — Génération patterns
        emails_candidats, contient_dirigeant = generer_tous_patterns(
            prenom=lead.dirigeant_prenom,
            nom=lead.dirigeant_nom,
            domaine=domaine_extrait,
            inclure_nominatifs=True,
            inclure_fonctionnels=True,
        )

        # Évite de redoublonner : si un pattern est déjà dans les scrapés,
        # on le retire des candidats
        if emails_scrapes and emails_candidats:
            scrapes_set = {e.lower() for e in emails_scrapes}
            emails_candidats = [e for e in emails_candidats if e.lower() not in scrapes_set]

        # Étape 3 — Source globale
        if emails_scrapes and emails_candidats:
            source = "scraping_et_patterns"
        elif emails_scrapes:
            source = "scraping_uniquement"
        elif emails_candidats:
            source = "patterns_uniquement"
        else:
            source = "aucun_email"

        return LeadStage3(
            **lead.model_dump(),
            emails_verifies=emails_scrapes,
            emails_candidats=emails_candidats,
            domaine_extrait=domaine_extrait,
            page_source_emails=page_source,
            nb_emails_verifies=len(emails_scrapes),
            nb_emails_candidats=len(emails_candidats),
            source_globale=source,
            contient_dirigeant_pattern=contient_dirigeant,
            signaux_ve=signaux_ve,
            linkedin_dirigeant_site=linkedin_dirigeant_site,
            linkedin_entreprise_site=linkedin_entreprise_site,
        )

    def _enrichir_un_lead_robuste(self, lead: LeadStage2) -> LeadStage3:
        """`_enrichir_un_lead` avec capture d'erreur → jamais d'exception remontée."""
        try:
            return self._enrichir_un_lead(lead)
        except Exception as e:  # noqa: BLE001
            logger.exception("Erreur sur lead %s : %s", lead.place_id, e)
            return LeadStage3(
                **lead.model_dump(),
                source_globale="aucun_email",
            )

    def enrichir(self, leads_l2: list[LeadStage2]) -> list[LeadStage3]:
        """Pipeline L2 → L3 sur une liste.

        Avec `max_workers > 1`, les leads sont scrapés en parallèle (le scraping
        est dominé par l'attente réseau). `ThreadPoolExecutor.map` préserve
        l'ordre d'entrée et la cadence de sauvegarde incrémentale ; la politesse
        par hôte reste garantie côté scraper.
        """
        logger.info("=== Étage 3 — Contacts (scraping + patterns) (%d leads) ===", len(leads_l2))
        t0 = time.monotonic()
        leads_l3: list[LeadStage3] = []

        nb_scraping_ok = 0
        nb_patterns_only = 0
        nb_aucun = 0
        nb_chaines_skip = 0

        parallele = self.max_workers > 1 and len(leads_l2) > 1
        if parallele:
            logger.info("  L3 en parallèle : %d workers", self.max_workers)
            executor = ThreadPoolExecutor(max_workers=self.max_workers)
            resultats = executor.map(self._enrichir_un_lead_robuste, leads_l2)
        else:
            executor = None
            resultats = (self._enrichir_un_lead_robuste(lead) for lead in leads_l2)

        for i, l3 in enumerate(resultats, start=1):
            leads_l3.append(l3)

            if l3.source_globale == "chaine_non_traitee":
                nb_chaines_skip += 1
            elif l3.nb_emails_verifies > 0:
                nb_scraping_ok += 1
            elif l3.nb_emails_candidats > 0:
                nb_patterns_only += 1
            else:
                nb_aucun += 1

            # Sauvegarde incrémentale
            if i % 20 == 0 and self.callback_save:
                logger.info("→ Sauvegarde incrémentale L3 (%d/%d)", i, len(leads_l2))
                try:
                    self.callback_save(leads_l3)
                except Exception as e:  # noqa: BLE001
                    logger.warning("Erreur sauvegarde incrémentale L3 : %s", e)

            if i % 25 == 0:
                logger.info("  L3 progress: %d/%d", i, len(leads_l2))

        if executor is not None:
            executor.shutdown(wait=True)

        duree = time.monotonic() - t0
        logger.info(
            "=== Étage 3 terminé : %d leads (%.1fs) ===\n"
            "  Au moins 1 email scrapé : %d (%.0f%%)\n"
            "  Patterns générés seuls : %d (%.0f%%)\n"
            "  Aucun email : %d (%.0f%%)\n"
            "  Chaînes ignorées : %d (%.0f%%)",
            len(leads_l2), duree,
            nb_scraping_ok, 100 * nb_scraping_ok / max(1, len(leads_l2)),
            nb_patterns_only, 100 * nb_patterns_only / max(1, len(leads_l2)),
            nb_aucun, 100 * nb_aucun / max(1, len(leads_l2)),
            nb_chaines_skip, 100 * nb_chaines_skip / max(1, len(leads_l2)),
        )

        return leads_l3

    @staticmethod
    def stats_l3(leads_l3: list[LeadStage3]) -> dict[str, Any]:
        n = len(leads_l3)
        if n == 0:
            return {"total": 0}
        nb_scrape = sum(1 for lead in leads_l3 if lead.nb_emails_verifies > 0)
        nb_au_moins_un = sum(
            1 for lead in leads_l3 if lead.nb_emails_verifies > 0 or lead.nb_emails_candidats > 0
        )
        nb_dirigeant = sum(1 for lead in leads_l3 if lead.contient_dirigeant_pattern)
        return {
            "total": n,
            "scrape_au_moins_un_email": nb_scrape,
            "scrape_pct": round(100 * nb_scrape / n, 1),
            "au_moins_un_email": nb_au_moins_un,
            "au_moins_un_pct": round(100 * nb_au_moins_un / n, 1),
            "dirigeant_pattern": nb_dirigeant,
            "dirigeant_pattern_pct": round(100 * nb_dirigeant / n, 1),
        }
