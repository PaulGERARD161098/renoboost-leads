"""Orchestrateur veille : CSV AAA → LeadVeille final.

Étapes :
1. Parse AAA Data (`parser_aaa`)
2. Filtre VE flotte entreprise (`filtre_ve_flotte`)
3. Anti-doublon flag (`etat_historique`)
4. Conversion en LeadStage2 (`adaptateur_lead_l2`)
5. Enrichissement L2 entreprise (réutilise `stage2_entreprises.enricher`)
6. Pipeline L3 (`stage3_contacts.enricher`)
7. Pipeline L4 (`stage4_prospection.enricher`)
8. Augmentation en LeadVeille (avec colonnes spécifiques veille)
9. Export CSV
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ..common.budget_guard import BudgetGuard
from ..common.cache import SessionCache
from ..common.logger import get_logger
from ..common.rate_limiter import RateLimiter
from ..models import ClaudeScoring, FiltresEntreprise, LeadStage4, LeadVeille
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
from .adaptateur_lead_l2 import lignaaa_vers_lead_stage1
from .etat_historique import EtatHistoriqueVE
from .filtre_ve_flotte import filtrer_lignes_aaa
from .models import LigneAAA, VeilleConfig
from .parser_aaa import lire_csv_aaa

logger = get_logger(__name__)


@dataclass
class ResultatVeille:
    """Résultat consolidé d'un cycle de veille."""

    date_run: str
    nb_lignes_brutes: int = 0
    nb_ve_flotte: int = 0
    nb_nouveaux: int = 0
    nb_deja_vus: int = 0
    nb_top_leads: int = 0
    cout_l4_eur: float = 0.0
    leads: list[LeadVeille] = field(default_factory=list)
    erreurs_parsing: list[str] = field(default_factory=list)
    rejets_filtre: dict[str, int] = field(default_factory=dict)


@dataclass
class VeilleRunConfig:
    """Paramètres d'un run de veille (équivalent du `CampaignConfig` côté CLI).

    Pour rester cohérent avec le pipeline classique, la veille réutilise
    `FiltresEntreprise` (filtre L2) et `ClaudeScoring` (config L4).
    """

    source_veille: str = "aaa_data"
    veille_config: VeilleConfig = field(default_factory=VeilleConfig)
    filtres_entreprise: FiltresEntreprise = field(default_factory=FiltresEntreprise)
    claude_scoring: ClaudeScoring = field(default_factory=ClaudeScoring)
    budget_eur: float = 5.0
    anthropic_api_key: str | None = None
    dry_run_l4: bool = False  # True = mock Claude, pas d'appel API
    rate_limit_per_min: int = 60


def _lead_stage4_vers_lead_veille(
    l4: LeadStage4,
    ligne_aaa: LigneAAA,
    source_veille: str,
    date_run: str,
    deja_eu_ve: bool,
    premiere_date_ve: str | None,
) -> LeadVeille:
    """Promote LeadStage4 → LeadVeille avec colonnes veille remplies.

    Fallback : si l'enrichissement L2 n'a pas retrouvé le SIREN (API en panne,
    pas de match nom+CP), on conserve le SIREN AAA Data qui est par construction
    fiable (issu du SIV via AAA Data).
    """
    payload = l4.model_dump()
    if not payload.get("siren") and ligne_aaa.siren:
        payload["siren"] = ligne_aaa.siren
    return LeadVeille(
        **payload,
        source_veille=source_veille,
        date_run_veille=date_run,
        date_immatriculation_ve=ligne_aaa.date_immatriculation.isoformat(),
        marque_ve=ligne_aaa.marque,
        modele_ve=ligne_aaa.modele,
        energie_ve=ligne_aaa.energie,
        type_vehicule_ve=ligne_aaa.type_vehicule,
        deja_eu_ve=deja_eu_ve,
        premiere_date_ve=premiere_date_ve,
    )


def executer_cycle_veille(
    fichier_aaa: Path,
    output_dir: Path,
    config: VeilleRunConfig,
    etat_db_path: Path | None = None,
) -> ResultatVeille:
    """Exécute un cycle de veille complet de bout en bout.

    Args:
        fichier_aaa: CSV AAA Data du jour
        output_dir: dossier où écrire les artefacts (cache, csv finaux, logs)
        config: paramètres du run
        etat_db_path: chemin du fichier état SIREN-vu. Par défaut placé dans
                      `output_dir.parent / etat_siren_ve.sqlite` — mutualisé entre
                      tous les runs pour la mémoire long terme.

    Returns:
        ResultatVeille consolidé (pour mailer / logs / monitoring)
    """
    t0 = time.monotonic()
    date_run = datetime.now().strftime("%Y-%m-%d")
    output_dir.mkdir(parents=True, exist_ok=True)
    resultat = ResultatVeille(date_run=date_run)

    # 1. Parse
    parse_result = lire_csv_aaa(fichier_aaa, config.veille_config)
    resultat.nb_lignes_brutes = parse_result.nb_lignes_brutes
    resultat.erreurs_parsing = list(parse_result.erreurs)
    logger.info("Veille : %d lignes brutes parsées", parse_result.nb_lignes_valides)

    # 2. Filtre VE flotte
    lignes_filtrees, rejets = filtrer_lignes_aaa(parse_result.lignes, config.veille_config)
    resultat.nb_ve_flotte = len(lignes_filtrees)
    resultat.rejets_filtre = rejets

    if not lignes_filtrees:
        logger.warning("Veille : aucun VE flotte entreprise dans %s", fichier_aaa.name)
        return resultat

    # 3. Anti-doublon (flag, pas d'exclusion)
    etat_path = etat_db_path or (output_dir.parent / "etat_siren_ve.sqlite")
    etat = EtatHistoriqueVE(etat_path)
    deja_vus_map: dict[str, tuple[bool, str | None]] = {}
    for ligne in lignes_filtrees:
        if ligne.siren is None:
            continue
        deja = etat.deja_vu(ligne.siren)
        deja_vus_map[ligne.siren] = (deja, None)  # premiere_date posée plus tard
    resultat.nb_deja_vus = sum(1 for v, _ in deja_vus_map.values() if v)
    resultat.nb_nouveaux = len(deja_vus_map) - resultat.nb_deja_vus

    # On marque tous les SIREN comme vus (ils seront "déjà vus" au prochain run)
    for ligne in lignes_filtrees:
        if ligne.siren:
            etat.marquer_vu(ligne.siren, ligne.date_immatriculation)

    # 4. Conversion en LeadStage1 (point d'entrée pipeline standard)
    leads_l1 = [lignaaa_vers_lead_stage1(lg) for lg in lignes_filtrees]

    # 5. Enrichissement L2 (recherche-entreprises.gouv.fr)
    cache = SessionCache(output_dir / "cache.sqlite")
    limiter = RateLimiter(config.rate_limit_per_min)
    rech_client = RechercheEntreprisesClient(RechercheClientConfig(rate_limiter=limiter))
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

    # 7. L4 — scoring
    if config.dry_run_l4:
        claude_client = ClaudeClientDryRun(
            modele=config.claude_scoring.modele,
            inclure_pitch=config.claude_scoring.inclure_pitch,
        )
    else:
        if not config.anthropic_api_key:
            raise RuntimeError("anthropic_api_key requise pour scoring L4 réel")
        claude_client = ClaudeClient(
            ClaudeClientConfig(
                api_key=config.anthropic_api_key,
                modele=config.claude_scoring.modele,
                max_tokens_sortie=config.claude_scoring.max_tokens_sortie,
                rate_limiter=limiter,
                budget=BudgetGuard(plafond_eur=config.budget_eur),
            )
        )
    cache_l4 = CacheStage4(output_dir / "cache_l4.sqlite")
    enricheur_l4 = EnricheurStage4(
        client=claude_client, config=config.claude_scoring, cache=cache_l4
    )
    leads_l4 = enricheur_l4.enrichir(leads_l3)
    resultat.cout_l4_eur = enricheur_l4.cout_total_eur

    # 8. Promote → LeadVeille
    # Associer chaque LeadStage4 à sa LigneAAA (même ordre garanti).
    leads_veille: list[LeadVeille] = []
    for l4, ligne_aaa in zip(leads_l4, lignes_filtrees, strict=True):
        deja, premiere_date = (False, None)
        if ligne_aaa.siren:
            deja, premiere_date = deja_vus_map.get(ligne_aaa.siren, (False, None))
        leads_veille.append(
            _lead_stage4_vers_lead_veille(
                l4=l4,
                ligne_aaa=ligne_aaa,
                source_veille=config.source_veille,
                date_run=date_run,
                deja_eu_ve=deja,
                premiere_date_ve=premiere_date,
            )
        )
    resultat.leads = leads_veille
    resultat.nb_top_leads = sum(1 for lv in leads_veille if lv.top_lead)

    duree = time.monotonic() - t0
    logger.info(
        "Veille terminée : %d top leads / %d VE flotte (%d nouveaux, %d déjà vus) "
        "en %.1fs, coût L4 %.4f €",
        resultat.nb_top_leads,
        resultat.nb_ve_flotte,
        resultat.nb_nouveaux,
        resultat.nb_deja_vus,
        duree,
        resultat.cout_l4_eur,
    )
    return resultat
