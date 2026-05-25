"""Orchestrateur étage 3.5 — L3 → L3.5 (enrichissement Dropcontact).

Logique :
1. Filtre intelligent : on ne sélectionne que les leads
   `hors_filtre_entreprise=False` (pas de gaspillage de crédits).
2. Pour chaque lead retenu :
   a. Cache lookup → hit = on hydrate sans appel API
   b. Cache miss → on bufferise pour appel batch
3. Quand le buffer atteint `batch_size` (ou en fin), on appelle
   `client.enrichir_batch` et on hydrate les leads.
4. Les leads non sélectionnés (hors filtre) sont passés tels quels en L3.5
   (champs Dropcontact = None).
5. Sauvegarde incrémentale après chaque lot.
"""

from __future__ import annotations

import time
from typing import Any, Protocol

from ..common.budget_guard import BudgetExceededError
from ..common.logger import get_logger
from ..models import EnrichissementL35, LeadStage3, LeadStage35
from .cache import CacheStage35, calcul_cache_key
from .client import (
    DropcontactError,
    DropcontactHostBlockedError,
    DropcontactReponse,
    lead_payload_dropcontact,
)

logger = get_logger(__name__)


class _ClientProto(Protocol):
    def enrichir_batch(self, lots: list[dict[str, Any]]) -> DropcontactReponse: ...


def _eligible(lead: LeadStage3) -> bool:
    """Filtre intelligent : on n'enrichit que si ça vaut le coup.

    Critères :
    - lead pas en hors-filtre entreprise
    - on a au moins un nom de dirigeant OU un site web (sinon Dropcontact
      ne pourra rien faire)
    - SIREN présent (Dropcontact donne de bien meilleurs résultats avec)
    """
    if lead.hors_filtre_entreprise:
        return False
    a_dirigeant = bool(lead.dirigeant_nom or lead.dirigeant_prenom)
    a_site = bool(lead.site_web or lead.domaine_extrait)
    a_siren = bool(lead.siren)
    return (a_dirigeant or a_site) and a_siren


def _extraire_email_dropcontact(item: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extrait (email, qualification) du champ 'email' Dropcontact.

    Format Dropcontact : `email = [{"email": "x@y.com", "qualification": "correct"}, ...]`
    On prend le premier email qualifié `correct` en priorité, sinon le premier.
    """
    emails = item.get("email") or []
    if not isinstance(emails, list) or not emails:
        return None, None
    correct = [e for e in emails if isinstance(e, dict) and e.get("qualification") == "correct"]
    cible = correct[0] if correct else emails[0]
    if not isinstance(cible, dict):
        return None, None
    return cible.get("email"), cible.get("qualification")


def _hydrater_lead(lead_l3: LeadStage3, item: dict[str, Any] | None) -> LeadStage35:
    """Construit un LeadStage35 à partir du L3 + réponse Dropcontact (ou None)."""
    base = lead_l3.model_dump()
    if item is None:
        return LeadStage35(**base, enrichi_dropcontact=False)

    email, qualif = _extraire_email_dropcontact(item)
    return LeadStage35(
        **base,
        email_dropcontact=email,
        qualification_email_dropcontact=qualif,
        telephone_direct_dropcontact=item.get("phone"),
        linkedin_dirigeant_dropcontact=item.get("linkedin"),
        linkedin_entreprise_dropcontact=item.get("company_linkedin"),
        civilite_dirigeant_dropcontact=item.get("civility"),
        prenom_dirigeant_dropcontact=item.get("first_name"),
        nom_dirigeant_dropcontact=item.get("last_name"),
        enrichi_dropcontact=True,
    )


def _payload_pour_lead(lead: LeadStage3) -> dict[str, Any]:
    """Construit le payload Dropcontact pour un lead."""
    domaine = lead.domaine_extrait or lead.site_web
    return lead_payload_dropcontact(
        first_name=lead.dirigeant_prenom,
        last_name=lead.dirigeant_nom,
        company=lead.nom,
        website=domaine,
        siren=lead.siren,
    )


class EnricheurStage35:
    """Pipeline L3 → L3.5 : enrichissement Dropcontact, batch + cache."""

    def __init__(
        self,
        client: _ClientProto,
        config: EnrichissementL35,
        cache: CacheStage35 | None = None,
        callback_save_incremental=None,
    ):
        self.client = client
        self.config = config
        self.cache = cache
        self.callback_save = callback_save_incremental

        self._cache_key = calcul_cache_key(
            provider=config.provider,
            language=config.language,
            siren=config.siren,
        )

        # Compteurs
        self.cache_hits = 0
        self.cache_misses = 0
        self.cout_total_eur = 0.0
        self.nb_envoyes = 0
        self.nb_enrichis = 0  # leads avec au moins email OU phone OU linkedin
        self.nb_filtres_out = 0
        self.nb_erreurs = 0
        self.nb_ignores_reseau = 0  # hôte bloqué par l'allowlist → skip propre

    def enrichir(self, leads_l3: list[LeadStage3]) -> list[LeadStage35]:
        logger.info(
            "=== Étage 3.5 — Enrichissement %s (%d leads, batch=%d) ===",
            self.config.provider,
            len(leads_l3),
            self.config.batch_size,
        )
        t0 = time.monotonic()
        # Pré-allocation pour préserver l'ordre
        resultats: list[LeadStage35 | None] = [None] * len(leads_l3)
        a_envoyer: list[tuple[int, LeadStage3]] = []
        budget_atteint = False

        # Pass 1 : cache + filtre
        for idx, lead in enumerate(leads_l3):
            if not _eligible(lead):
                self.nb_filtres_out += 1
                resultats[idx] = _hydrater_lead(lead, None)
                continue

            if self.cache:
                cached = self.cache.get(lead.place_id, self._cache_key)
                if cached is not None:
                    self.cache_hits += 1
                    l35 = _hydrater_lead(lead, cached)
                    if l35.email_dropcontact or l35.telephone_direct_dropcontact:
                        self.nb_enrichis += 1
                    resultats[idx] = l35
                    continue

            self.cache_misses += 1
            a_envoyer.append((idx, lead))

        # Pass 2 : batchs
        i = 0
        while i < len(a_envoyer) and not budget_atteint:
            batch = a_envoyer[i : i + self.config.batch_size]
            lots = [_payload_pour_lead(lead) for _, lead in batch]
            self.nb_envoyes += len(lots)

            try:
                reponse = self.client.enrichir_batch(lots)
            except DropcontactHostBlockedError as e:
                # Hôte injoignable (allowlist) : inutile de retenter les lots
                # suivants, le même hôte restera bloqué. On ignore proprement
                # tout le reste et on passe les leads sans enrichissement.
                restants = a_envoyer[i:]
                self.nb_envoyes -= len(batch)  # lot courant jamais réellement traité
                logger.warning(
                    "Étage 3.5 ignoré : hôte Dropcontact bloqué par la politique "
                    "réseau (allowlist) — %d lead(s) passé(s) sans enrichissement. "
                    "Détail : %s",
                    len(restants),
                    e,
                )
                for idx, lead in restants:
                    resultats[idx] = LeadStage35(
                        **lead.model_dump(),
                        enrichi_dropcontact=False,
                        enrichissement_erreur="reseau_indisponible: hote_bloque_allowlist",
                    )
                self.nb_ignores_reseau += len(restants)
                budget_atteint = True  # réutilise le drapeau d'arrêt de boucle
                break
            except BudgetExceededError as e:
                logger.error("L3.5 stoppé par budget guard : %s", e)
                budget_atteint = True
                # Les leads restants partent sans enrichissement (mais flag erreur)
                for idx, lead in a_envoyer[i:]:
                    resultats[idx] = LeadStage35(
                        **lead.model_dump(),
                        enrichi_dropcontact=False,
                        enrichissement_erreur=f"budget_exhausted: {e}",
                    )
                self.nb_erreurs += len(a_envoyer) - i
                break
            except DropcontactError as e:
                logger.warning("Erreur Dropcontact sur batch (%d leads) : %s", len(batch), e)
                # On marque ces leads en erreur mais on continue
                for idx, lead in batch:
                    resultats[idx] = LeadStage35(
                        **lead.model_dump(),
                        enrichi_dropcontact=False,
                        enrichissement_erreur=f"api_error: {e}",
                    )
                self.nb_erreurs += len(batch)
                i += self.config.batch_size
                continue
            except Exception as e:  # noqa: BLE001
                logger.exception("Erreur inattendue L3.5 batch : %s", e)
                for idx, lead in batch:
                    resultats[idx] = LeadStage35(
                        **lead.model_dump(),
                        enrichi_dropcontact=False,
                        enrichissement_erreur=f"unexpected: {type(e).__name__}",
                    )
                self.nb_erreurs += len(batch)
                i += self.config.batch_size
                continue

            self.cout_total_eur += reponse.cout_eur

            # Hydrate les leads dans l'ordre du batch
            for (idx, lead), item in zip(batch, reponse.data, strict=False):
                l35 = _hydrater_lead(lead, item)
                # Stocke en cache (même si vide, ça évite de re-payer)
                if self.cache:
                    self.cache.store(lead.place_id, self._cache_key, item)
                if l35.email_dropcontact or l35.telephone_direct_dropcontact:
                    self.nb_enrichis += 1
                # Coût par lead (réparti uniformément sur le batch)
                cout_lead = reponse.cout_eur / len(batch) if batch else 0.0
                l35.cout_enrichissement_eur = cout_lead
                resultats[idx] = l35

            # Callback de sauvegarde incrémentale après chaque batch
            if self.callback_save:
                # On ne sauvegarde que les leads déjà résolus (None → on saute)
                partiels = [r for r in resultats if r is not None]
                try:
                    self.callback_save(partiels)
                except Exception as e:  # noqa: BLE001
                    logger.warning("Erreur sauvegarde incrémentale L3.5 : %s", e)

            i += self.config.batch_size

        # Pass 3 : sécurité — tout lead resté à None (ne devrait pas arriver) → fallback
        for idx, lead in enumerate(leads_l3):
            if resultats[idx] is None:
                resultats[idx] = _hydrater_lead(lead, None)

        leads_l35: list[LeadStage35] = [r for r in resultats if r is not None]
        duree = time.monotonic() - t0
        logger.info(
            "=== Étage 3.5 terminé : %d leads (%.1fs) ===\n"
            "  Filtrés (hors filtre / inéligibles) : %d\n"
            "  Cache hits / miss : %d / %d\n"
            "  Envoyés à l'API : %d (enrichis : %d, erreurs : %d)\n"
            "  Ignorés (réseau indisponible) : %d\n"
            "  Coût total : %.2f €",
            len(leads_l35),
            duree,
            self.nb_filtres_out,
            self.cache_hits,
            self.cache_misses,
            self.nb_envoyes,
            self.nb_enrichis,
            self.nb_erreurs,
            self.nb_ignores_reseau,
            self.cout_total_eur,
        )
        return leads_l35

    def stats_l35(self, leads_l35: list[LeadStage35]) -> dict[str, Any]:
        n = len(leads_l35)
        if n == 0:
            return {"total": 0}
        avec_email = sum(1 for lead in leads_l35 if lead.email_dropcontact)
        avec_phone = sum(1 for lead in leads_l35 if lead.telephone_direct_dropcontact)
        avec_linkedin = sum(
            1
            for lead in leads_l35
            if lead.linkedin_dirigeant_dropcontact or lead.linkedin_entreprise_dropcontact
        )
        return {
            "total": n,
            "filtres_out": self.nb_filtres_out,
            "envoyes_api": self.nb_envoyes,
            "enrichis": self.nb_enrichis,
            "erreurs": self.nb_erreurs,
            "ignores_reseau": self.nb_ignores_reseau,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cout_total_eur": round(self.cout_total_eur, 4),
            "avec_email_pct": round(100 * avec_email / n, 1),
            "avec_phone_pct": round(100 * avec_phone / n, 1),
            "avec_linkedin_pct": round(100 * avec_linkedin / n, 1),
        }
