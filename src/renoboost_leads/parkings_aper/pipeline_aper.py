"""Orchestrateur parkings APER : CSV inventaire → LeadAper final.

Étapes :
1. Parse inventaire parkings (`parser_parkings`)
2. Filtre surface > seuil APER (`filtre_parkings`)
3. Anti-doublon flag (`etat_historique`)
4. Conversion en LeadStage1 (`adaptateur_lead_l2`)
5. Enrichissement L2 entreprise (réutilise `stage2_entreprises.enricher`)
6. Pipeline L3 (`stage3_contacts.enricher`)
7. Pipeline L4 scoring Claude (`stage4_prospection.enricher`)
8. Promotion en LeadAper (colonnes APER : surface, échéance, priorité)
9. Export CSV

Réutilise tout le pipeline RénoBoost existant. Le contexte réglementaire APER
est injecté dans le scoring L4 (sauf si un `contexte_client` est déjà fourni).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from ..common.budget_guard import BudgetGuard
from ..common.cache import SessionCache
from ..common.logger import get_logger
from ..common.rate_limiter import RateLimiter
from ..models import ClaudeScoring, FiltresEntreprise, LeadAper, LeadStage4
from ..stage2_entreprises.enricher import EnricheurStage2
from ..stage2_entreprises.recherche_client import (
    RechercheClientConfig,
    RechercheEntreprisesClient,
)
from ..stage3_contacts.enricher import EnricheurStage3
from ..stage3_contacts.scraper import ScraperContact
from ..stage4_prospection.cache import CacheStage4
from ..stage4_prospection.client import ClaudeClient, ClaudeClientConfig
from ..stage4_prospection.dry_run import ClaudeClientDryRun
from ..stage4_prospection.enricher import EnricheurStage4
from ..veille_immatriculations.mailer import ConfigSMTP
from .adaptateur_lead_l2 import ligne_parking_vers_lead_stage1
from .etat_historique import EtatHistoriqueParkings
from .exporter_aper import export_aper_csv
from .filtre_parkings import filtrer_parkings
from .mailer import ResumeAper, envoyer_resume_aper
from .matching_geo import resoudre_lignes_sans_enseigne
from .models import AperConfig, LigneParking
from .parser_parkings import lire_csv_parkings

logger = get_logger(__name__)


CONTEXTE_APER_DEFAUT = (
    "Rossini Energy conçoit et installe des ombrières photovoltaïques et des "
    "bornes de recharge pour véhicules électriques. CIBLE : exploitants de parcs "
    "de stationnement extérieurs de plus de 1 500 m², désormais soumis à "
    "l'OBLIGATION LÉGALE de solarisation (art. 40 loi APER, décret 2024-1023) : "
    "ils doivent couvrir 50 % de leur parking d'ombrières PV avant le 1er juillet "
    "2026 (parkings > 10 000 m²) ou 2028 (1 500 – 10 000 m²), sous peine d'amende "
    "jusqu'à 40 000 €/an. Ce sont des prospects contraints et datés : score élevé "
    "si grande surface + échéance proche."
)


@dataclass
class ResultatAper:
    """Résultat consolidé d'un run parkings APER."""

    date_run: str
    nb_lignes_brutes: int = 0
    nb_parkings_aper: int = 0
    nb_nouveaux: int = 0
    nb_deja_vus: int = 0
    nb_top_leads: int = 0
    nb_resolus_geo: int = 0  # Phase C : parkings sans enseigne résolus par géoloc
    cout_l4_eur: float = 0.0
    leads: list[LeadAper] = field(default_factory=list)
    erreurs_parsing: list[str] = field(default_factory=list)
    rejets_filtre: dict[str, int] = field(default_factory=dict)


@dataclass
class AperRunConfig:
    """Paramètres d'un run parkings APER."""

    source_aper: str = "aper_osm"
    aper_config: AperConfig = field(default_factory=AperConfig)
    filtres_entreprise: FiltresEntreprise = field(default_factory=FiltresEntreprise)
    claude_scoring: ClaudeScoring = field(default_factory=ClaudeScoring)
    budget_eur: float = 5.0
    anthropic_api_key: str | None = None
    dry_run_l4: bool = False
    rate_limit_per_min: int = 60
    # Phase C : résolution géoloc → SIREN des parkings sans enseigne
    resoudre_geo: bool = True
    rayon_geo_km: float = 0.2
    # Phase D : email récapitulatif post-run (None = pas d'envoi)
    smtp_config: ConfigSMTP | None = None


def _lead_stage4_vers_lead_aper(
    l4: LeadStage4,
    ligne: LigneParking,
    source_aper: str,
    date_run: str,
    deja_vu: bool,
) -> LeadAper:
    """Promote LeadStage4 → LeadAper avec colonnes parking remplies.

    Fallback SIREN : si l'enrichissement L2 n'a rien retrouvé mais que la ligne
    parking portait déjà un SIREN (fichier client), on le conserve.
    """
    payload = l4.model_dump()
    if not payload.get("siren") and ligne.siren:
        payload["siren"] = ligne.siren
    echeance, priorite = ligne.echeance()
    return LeadAper(
        **payload,
        source_aper=source_aper,
        date_run_aper=date_run,
        identifiant_parking=ligne.identifiant_stable(),
        surface_parking_m2=ligne.surface_m2,
        surface_ombrable_m2=ligne.surface_ombrable_m2,
        nb_places_estime=ligne.nb_places_estime,
        echeance_aper=echeance,
        priorite_aper=priorite,
        deja_vu_parking=deja_vu,
    )


def _claude_scoring_avec_contexte(base: ClaudeScoring) -> ClaudeScoring:
    """Injecte le contexte réglementaire APER si aucun contexte n'est fourni."""
    if base.contexte_client:
        return base
    return base.model_copy(update={"contexte_client": CONTEXTE_APER_DEFAUT})


def executer_cycle_aper(
    fichier_parkings: Path,
    output_dir: Path,
    config: AperRunConfig,
    etat_db_path: Path | None = None,
) -> ResultatAper:
    """Exécute un cycle parkings APER complet de bout en bout."""
    t0 = time.monotonic()
    date_run = datetime.now().strftime("%Y-%m-%d")
    output_dir.mkdir(parents=True, exist_ok=True)
    resultat = ResultatAper(date_run=date_run)

    # 1. Parse
    parse_result = lire_csv_parkings(fichier_parkings, config.aper_config)
    resultat.nb_lignes_brutes = parse_result.nb_lignes_brutes
    resultat.erreurs_parsing = list(parse_result.erreurs)
    logger.info("APER : %d lignes brutes parsées", parse_result.nb_lignes_valides)

    # 2. Filtre surface
    lignes_filtrees, rejets = filtrer_parkings(parse_result.lignes, config.aper_config)
    resultat.nb_parkings_aper = len(lignes_filtrees)
    resultat.rejets_filtre = rejets

    if not lignes_filtrees:
        logger.warning("APER : aucun parking soumis à l'obligation dans %s",
                       fichier_parkings.name)
        return resultat

    # Client recherche-entreprises (gratuit) — partagé Phase C + L2.
    limiter = RateLimiter(config.rate_limit_per_min)
    rech_client = RechercheEntreprisesClient(RechercheClientConfig(rate_limiter=limiter))

    # 2.5 Phase C — résolution géoloc → SIREN des parkings sans enseigne, AVANT
    # l'anti-doublon (l'identifiant stable devient SIREN une fois résolu).
    if config.resoudre_geo:
        stats_geo = resoudre_lignes_sans_enseigne(
            lignes_filtrees, rech_client, rayon_km=config.rayon_geo_km
        )
        resultat.nb_resolus_geo = stats_geo["resolu"]

    # 3. Anti-doublon (flag, pas d'exclusion)
    etat_path = etat_db_path or (output_dir.parent / "etat_parkings.sqlite")
    etat = EtatHistoriqueParkings(etat_path)
    deja_vu_map: dict[str, bool] = {}
    today = date.today()
    for ligne in lignes_filtrees:
        ident = ligne.identifiant_stable()
        deja_vu_map[ident] = etat.deja_vu(ident)
    resultat.nb_deja_vus = sum(1 for v in deja_vu_map.values() if v)
    resultat.nb_nouveaux = len(deja_vu_map) - resultat.nb_deja_vus
    for ligne in lignes_filtrees:
        etat.marquer_vu(ligne.identifiant_stable(), today)

    # 4. Conversion en LeadStage1
    leads_l1 = [ligne_parking_vers_lead_stage1(lg) for lg in lignes_filtrees]

    # 5. L2 — enrichissement entreprise (réutilise le client créé pour la Phase C)
    cache = SessionCache(output_dir / "cache.sqlite")
    enricheur_l2 = EnricheurStage2(
        client=rech_client,
        cache=cache,
        filtres_entreprise=config.filtres_entreprise,
    )
    leads_l2 = enricheur_l2.enrichir(leads_l1)

    # 6. L3 — scraping contacts
    scraper = ScraperContact(rate_limit_seconds=1.0)
    enricheur_l3 = EnricheurStage3(scraper=scraper, cache=cache)
    leads_l3 = enricheur_l3.enrichir(leads_l2)

    # 7. L4 — scoring (contexte APER injecté)
    claude_scoring = _claude_scoring_avec_contexte(config.claude_scoring)
    if config.dry_run_l4:
        claude_client = ClaudeClientDryRun(
            modele=claude_scoring.modele,
            inclure_pitch=claude_scoring.inclure_pitch,
        )
    else:
        if not config.anthropic_api_key:
            raise RuntimeError("anthropic_api_key requise pour scoring L4 réel")
        claude_client = ClaudeClient(
            ClaudeClientConfig(
                api_key=config.anthropic_api_key,
                modele=claude_scoring.modele,
                max_tokens_sortie=claude_scoring.max_tokens_sortie,
                rate_limiter=limiter,
                budget=BudgetGuard(plafond_eur=config.budget_eur),
            )
        )
    cache_l4 = CacheStage4(output_dir / "cache_l4.sqlite")
    enricheur_l4 = EnricheurStage4(
        client=claude_client, config=claude_scoring, cache=cache_l4
    )
    leads_l4 = enricheur_l4.enrichir(leads_l3)
    resultat.cout_l4_eur = enricheur_l4.cout_total_eur

    # 8. Promote → LeadAper
    leads_aper: list[LeadAper] = []
    for l4, ligne in zip(leads_l4, lignes_filtrees, strict=True):
        deja = deja_vu_map.get(ligne.identifiant_stable(), False)
        leads_aper.append(
            _lead_stage4_vers_lead_aper(
                l4=l4,
                ligne=ligne,
                source_aper=config.source_aper,
                date_run=date_run,
                deja_vu=deja,
            )
        )
    resultat.leads = leads_aper
    resultat.nb_top_leads = sum(1 for la in leads_aper if la.top_lead)

    # 9. Export CSV final
    csv_final = output_dir / "parkings_aper_leads.csv"
    export_aper_csv(leads_aper, csv_final)

    duree = time.monotonic() - t0
    logger.info(
        "APER terminé : %d top leads / %d parkings (%d nouveaux, %d déjà vus) "
        "en %.1fs, coût L4 %.4f €",
        resultat.nb_top_leads,
        resultat.nb_parkings_aper,
        resultat.nb_nouveaux,
        resultat.nb_deja_vus,
        duree,
        resultat.cout_l4_eur,
    )

    # 10. Phase D — email récapitulatif post-run (si SMTP configuré)
    if config.smtp_config is not None:
        try:
            _envoyer_resume(resultat, csv_final, config.smtp_config)
        except Exception as e:  # noqa: BLE001
            logger.exception("Envoi email APER post-run échoué : %s", e)

    return resultat


def _envoyer_resume(
    resultat: ResultatAper, csv_final: Path, smtp_config: ConfigSMTP
) -> None:
    """Construit un ResumeAper à partir du ResultatAper et l'envoie."""
    extraits = [
        {
            "nom": la.nom or "?",
            "siren": la.siren or "?",
            "score": str(la.score_interet) if la.score_interet is not None else "—",
            "surface": str(int(la.surface_parking_m2)),
            "echeance": la.echeance_aper or "?",
            "priorite": la.priorite_aper or "?",
            "raison": (la.raison_score or "")[:120],
        }
        for la in sorted(
            resultat.leads, key=lambda la: la.score_interet or 0, reverse=True
        )
        if la.top_lead
    ]
    resume = ResumeAper(
        date_run=resultat.date_run,
        nb_lignes_brutes=resultat.nb_lignes_brutes,
        nb_parkings_aper=resultat.nb_parkings_aper,
        nb_nouveaux=resultat.nb_nouveaux,
        nb_deja_vus=resultat.nb_deja_vus,
        nb_top_leads=resultat.nb_top_leads,
        cout_l4_eur=resultat.cout_l4_eur,
        chemin_csv=csv_final,
        extraits_top=extraits,
    )
    envoyer_resume_aper(smtp_config, resume)
