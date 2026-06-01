"""Orchestrateur réutilisable du pipeline L0→L4.

Extrait de `cli.run` pour être appelé à l'identique par la CLI **et** par le
worker Railway (`WORKER_MODE=real`). La CLI conserve ses responsabilités propres
(résolution du dossier de sortie, registre RGPD, run_stats.json, upload Storage,
résumé console) ; l'orchestrateur ne s'occupe que du *séquençage des étages*.

Le comportement par étage est strictement celui de la CLI : les helpers
`_executer_stageN` y ont été déplacés sans modification. Un callback `emit`
optionnel permet au worker de suivre la progression (étape lisible, 0-100,
counts) sans coupler l'orchestrateur à Supabase.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from logging import Logger, getLogger
from pathlib import Path
from typing import Any

from rich.console import Console

from .common.budget_guard import BudgetExceededError, BudgetGuard
from .common.cache import SessionCache
from .common.rate_limiter import RateLimiter
from .completion import (
    EtageCompletion,
    construire_provider_societeinfo,
    export_completion_csv,
    generer_annexe_completion,
)
from .exporter import (
    backup_csv,
    export_stage1_csv,
    export_stage2_csv,
    export_stage3_5_csv,
    export_stage3_csv,
    export_stage3_csv_separe_hors_filtre,
    export_stage4_csv,
    lire_stage1_csv,
    lire_stage2_csv,
    lire_stage3_5_csv,
    lire_stage3_csv,
)
from .models import RunStats, StageStats
from .settings import get_settings
from .societeinfo_enrichment.client import (
    SocieteinfoClient,
    SocieteinfoClientConfig,
    SocieteinfoClientDryRun,
)
from .stage0_sirene_first.extractor import ExtracteurStage0
from .stage0_sirene_first.geocoder import BANGeocoder, GeocoderConfig
from .stage0_sirene_first.places_enricher import EnrichisseurPlaces
from .stage1_decouverte.extractor import ExtracteurStage1
from .stage1_decouverte.places_client import PlacesClient, PlacesClientConfig
from .stage2_entreprises.enricher import EnricheurStage2
from .stage2_entreprises.pappers_client import PappersClient, PappersClientConfig
from .stage2_entreprises.recherche_client import (
    RechercheClientConfig,
    RechercheEntreprisesClient,
)
from .stage2_entreprises.societeinfo_l2_client import SocieteinfoL2Client
from .stage3_5_enrichment.cache import CacheStage35
from .stage3_5_enrichment.client import DropcontactClient, DropcontactClientConfig
from .stage3_5_enrichment.dry_run import DropcontactClientDryRun
from .stage3_5_enrichment.enricher import EnricheurStage35
from .stage3_contacts.enricher import EnricheurStage3
from .stage3_contacts.scraper import ScraperContact
from .stage4_prospection.cache import CacheStage4
from .stage4_prospection.client import ClaudeClient, ClaudeClientConfig
from .stage4_prospection.dry_run import ClaudeClientDryRun
from .stage4_prospection.enricher import EnricheurStage4

console = Console()

# Callback de progression : (etape lisible, progress 0-100, counts).
EmitFn = Callable[[str, int, dict[str, int]], None]


def _check_google_key_or_exit() -> str:
    settings = get_settings()
    if not settings.has_google_places():
        console.print(
            "[red]✗ GOOGLE_PLACES_API_KEY manquante.[/red] "
            "Crée un fichier .env (cf. .env.example) et colle ta clé."
        )
        sys.exit(2)
    return settings.google_places_api_key.get_secret_value()


# ════════════════════════════════════════════════════════════════
# Sous-fonctions par étage (déplacées depuis cli.py — comportement identique)
# ════════════════════════════════════════════════════════════════


def _executer_stage0(
    cfg, settings, output_dir, stats, *, enrichir_avec_places: bool, dry_run: bool
):
    """Découverte SIRENE-first : recherche-entreprises.api.gouv + (optionnel) enrichissement Places.

    Renvoie une liste de LeadStage2 (déjà enrichis SIREN/NAF/CA/effectif/etc.).
    Écrit `etage2_entreprises.csv` directement (les leads sont stage2 dès la sortie de stage 0).
    Écrit aussi `etage0_decouverte_sirene.csv` pour traçabilité.
    """
    if dry_run:
        from .models import LeadStage2
        leads: list[LeadStage2] = [
            LeadStage2(
                place_id=f"sirene:{i:09d}",
                extraction_date=datetime.now(timezone.utc),
                nom=f"Test PME {i} SAS",
                ville="Lille",
                code_postal="59000",
                pays="France",
                siren=f"{i:09d}",
                siret=f"{i:09d}00015",
                code_naf="49.41A",
                tranche_effectif="11",
                categorie_entreprise="PME",
                chiffre_affaires=1_500_000,
                statut_actif=True,
                score_matching=100.0,
            )
            for i in range(min(10, cfg.volume.cible))
        ]
        cout_eur = 0.0
        nb_appels = 0
    else:
        t0 = datetime.now(timezone.utc)
        limiter = RateLimiter(settings.max_requests_per_minute)
        recherche_client = RechercheEntreprisesClient(
            RechercheClientConfig(rate_limiter=limiter)
        )
        # Géocodeur BAN : utilisé seulement si zone='point' est définie par une
        # adresse en clair (sans latitude/longitude). Construit dans tous les cas
        # (sans coût ni appel réseau tant que .geocoder() n'est pas invoqué).
        geocoder = BANGeocoder(
            GeocoderConfig(rate_limiter=RateLimiter(settings.max_requests_per_minute))
        )
        extracteur = ExtracteurStage0(
            client=recherche_client, config=cfg, geocoder=geocoder
        )
        leads = extracteur.extraire()

        cout_eur = 0.0  # API recherche-entreprises = gratuite
        nb_appels = 0  # non instrumenté ici (côté wrapper si besoin)

        duree = (datetime.now(timezone.utc) - t0).total_seconds()
        stats.etages_executes.append(
            StageStats(
                nom_etage="stage0_sirene_decouverte",
                duree_secondes=duree,
                nb_appels_api=nb_appels,
                nb_succes=len(leads),
                nb_echecs=0,
                cout_eur_estime=cout_eur,
                leads_collectes=len(leads),
            )
        )

    # Traçabilité : CSV brut de la découverte SIRENE
    csv_decouverte = output_dir / "etage0_decouverte_sirene.csv"
    export_stage2_csv(leads, csv_decouverte)
    backup_csv(csv_decouverte)
    console.print(f"[green]✓ Étage 0 (SIRENE) : {len(leads)} leads → {csv_decouverte.name}[/green]")

    # Enrichissement Places ciblé (optionnel)
    if enrichir_avec_places and not dry_run and leads:
        t0 = datetime.now(timezone.utc)
        api_key = _check_google_key_or_exit()
        budget = BudgetGuard(plafond_eur=cfg.budget.max_eur)
        places_limiter = RateLimiter(settings.max_requests_per_minute)
        places_client = PlacesClient(
            PlacesClientConfig(api_key=api_key, rate_limiter=places_limiter, budget=budget)
        )
        enrichisseur = EnrichisseurPlaces(client=places_client)

        leads_enrichis = enrichisseur.enrichir_lot(leads)
        nb_avec_site = sum(1 for lead in leads_enrichis if lead.site_web)
        leads = leads_enrichis

        duree = (datetime.now(timezone.utc) - t0).total_seconds()
        stats.cout_total_eur += budget.cout_actuel_eur
        stats.etages_executes.append(
            StageStats(
                nom_etage="stage0_places_enrichissement",
                duree_secondes=duree,
                nb_appels_api=budget.nb_appels,
                nb_succes=nb_avec_site,
                nb_echecs=len(leads) - nb_avec_site,
                cout_eur_estime=budget.cout_actuel_eur,
                leads_collectes=len(leads),
            )
        )
        console.print(
            f"[green]✓ Enrichissement Places : {nb_avec_site}/{len(leads)} leads "
            f"avec site web ({budget.cout_actuel_eur:.2f} €)[/green]"
        )

    # CSV principal pour la suite du pipeline (équivalent stage 2)
    csv_l2 = output_dir / "etage2_entreprises.csv"
    export_stage2_csv(leads, csv_l2)
    backup_csv(csv_l2)
    console.print(f"[green]✓ Étage 0 → CSV stage2 : {csv_l2.name}[/green]")
    return leads


def _executer_stage1(cfg, settings, cache, output_dir, stats, dry_run):
    """Exécute l'étage 1 et retourne la liste des leads L1."""
    if dry_run:
        from .models import LeadStage1

        leads = [
            LeadStage1(
                place_id=f"FAKE_{i}",
                extraction_date=datetime.now(timezone.utc),
                nom=f"Établissement test {i}",
                adresse=f"{i} rue Fictive, 13000 Marseille",
                ville="Marseille",
                code_postal="13000",
                site_web=f"https://test-{i}.example.fr",
                note=4.2,
                nb_avis=42,
            )
            for i in range(min(10, cfg.volume.cible))
        ]
    else:
        api_key = _check_google_key_or_exit()
        t0 = datetime.now(timezone.utc)
        limiter = RateLimiter(settings.max_requests_per_minute)
        budget = BudgetGuard(plafond_eur=cfg.budget.max_eur)
        client = PlacesClient(
            PlacesClientConfig(api_key=api_key, rate_limiter=limiter, budget=budget)
        )
        extracteur = ExtracteurStage1(client=client, config=cfg, cache=cache)

        try:
            leads = extracteur.extraire()
        except BudgetExceededError as e:
            console.print(f"[red]✗ Budget dépassé : {e}[/red]")
            leads = []

        duree = (datetime.now(timezone.utc) - t0).total_seconds()
        stats.cout_total_eur += budget.cout_actuel_eur
        stats.etages_executes.append(
            StageStats(
                nom_etage="stage1_decouverte",
                duree_secondes=duree,
                nb_appels_api=budget.nb_appels,
                nb_succes=len(leads),
                nb_echecs=0,
                cout_eur_estime=budget.cout_actuel_eur,
                leads_collectes=len(leads),
            )
        )

    csv_path = output_dir / "etage1_decouverte.csv"
    export_stage1_csv(leads, csv_path)
    backup_csv(csv_path)
    console.print(f"\n[green]✓ Étage 1 : {len(leads)} leads → {csv_path.name}[/green]")
    return leads


def _construire_client_l2_societeinfo(cfg, settings, stats, dry_run: bool) -> SocieteinfoL2Client:
    """Fabrique l'adaptateur L2 Societeinfo (réel ou dry-run selon clé/flag)."""
    use_dry = dry_run or not settings.has_societeinfo()
    if use_dry and not dry_run:
        console.print(
            "[yellow]⚠  SOCIETEINFO_API_KEY absente → L2 Societeinfo en dry-run "
            "(données simulées).[/yellow]"
        )
    if use_dry:
        si_client: SocieteinfoClient = SocieteinfoClientDryRun()
    else:
        budget_eur = max(0.01, cfg.budget.max_eur - stats.cout_total_eur)
        si_client = SocieteinfoClient(
            SocieteinfoClientConfig(
                api_key=settings.societeinfo_api_key.get_secret_value(),
                rate_limiter=RateLimiter(settings.max_requests_per_minute),
                budget=BudgetGuard(plafond_eur=budget_eur),
            )
        )
    return SocieteinfoL2Client(si_client)


def _executer_stage2(
    cfg, settings, leads_l1, cache, output_dir, stats,
    l2_provider: str = "datagouv", dry_run: bool = False,
):
    """Exécute l'étage 2 (provider data.gouv par défaut, ou Societeinfo)."""
    csv_path = output_dir / "etage2_entreprises.csv"
    t0 = datetime.now(timezone.utc)

    def callback_save(leads_partial):
        export_stage2_csv(leads_partial, csv_path)

    limiter = RateLimiter(60)  # 60 req/min, largement sous la limite de 7 req/s
    if l2_provider == "societeinfo":
        rech_client = _construire_client_l2_societeinfo(cfg, settings, stats, dry_run)
        console.print("[cyan]ℹ  Provider L2 : Societeinfo (registres officiels).[/cyan]")
    else:
        rech_client = RechercheEntreprisesClient(RechercheClientConfig(rate_limiter=limiter))

    # Fallback Pappers (PAYANT) : activé uniquement si une clé est présente.
    pappers_client = None
    if settings.has_pappers():
        budget_pappers = BudgetGuard(
            plafond_eur=max(0.01, cfg.budget.max_eur - stats.cout_total_eur)
        )
        pappers_client = PappersClient(
            PappersClientConfig(
                api_key=settings.pappers_api_key.get_secret_value(),
                cout_par_appel_eur=settings.pappers_cout_par_appel_eur,
                rate_limiter=RateLimiter(settings.max_requests_per_minute),
                budget=budget_pappers,
            )
        )
        console.print("[cyan]ℹ  Fallback Pappers activé pour les matches incertains.[/cyan]")

    enricheur = EnricheurStage2(
        client=rech_client,
        cache=cache,
        callback_save_incremental=callback_save,
        filtres_entreprise=cfg.filtres_entreprise,
        pappers_client=pappers_client,
    )

    leads_l2 = enricheur.enrichir(leads_l1)
    duree = (datetime.now(timezone.utc) - t0).total_seconds()

    # Sauvegarde finale
    export_stage2_csv(leads_l2, csv_path)
    backup_csv(csv_path)

    # Stats
    stats_e2 = enricheur.stats_l2(leads_l2)
    stats.cout_total_eur += enricheur.cout_pappers_eur
    stats.etages_executes.append(
        StageStats(
            nom_etage="stage2_entreprises",
            duree_secondes=duree,
            nb_appels_api=stats_e2.get("total", 0) - stats_e2.get("chaines", 0),
            nb_succes=stats_e2.get("siren_trouve", 0),
            nb_echecs=(
                stats_e2.get("total", 0)
                - stats_e2.get("siren_trouve", 0)
                - stats_e2.get("chaines", 0)
            ),
            cout_eur_estime=enricheur.cout_pappers_eur,
            leads_collectes=len(leads_l2),
        )
    )

    msg_pappers = ""
    if enricheur.nb_fallback_pappers:
        msg_pappers = (
            f"\n   Fallback Pappers : {enricheur.nb_fallback_pappers} appels "
            f"({enricheur.cout_pappers_eur:.2f} €)"
        )
    console.print(
        f"\n[green]✓ Étage 2 : {len(leads_l2)} leads enrichis → {csv_path.name}[/green]\n"
        f"   SIREN trouvé : {stats_e2.get('siren_pct', 0)}% — "
        f"Dirigeant trouvé : {stats_e2.get('dirigeant_pct', 0)}% — "
        f"Chaînes : {stats_e2.get('chaines_pct', 0)}%"
        f"{msg_pappers}"
    )
    return leads_l2


def _executer_stage3(cfg, leads_l2, cache, output_dir, stats):
    """Exécute l'étage 3."""
    csv_path = output_dir / "etage3_contacts.csv"
    t0 = datetime.now(timezone.utc)

    def callback_save(leads_partial):
        export_stage3_csv(leads_partial, csv_path)

    scraper = ScraperContact(
        rate_limit_seconds=1.0,
        signaux_ve=cfg.scraping_l3.signaux_ve,
    )
    enricheur = EnricheurStage3(
        scraper=scraper,
        cache=cache,
        callback_save_incremental=callback_save,
    )

    leads_l3 = enricheur.enrichir(leads_l2)
    duree = (datetime.now(timezone.utc) - t0).total_seconds()

    # B3 : split qualifiés / hors-filtre si au moins un lead flagué.
    # Sinon, comportement historique (un seul CSV).
    p_main, p_hf = export_stage3_csv_separe_hors_filtre(leads_l3, csv_path)
    backup_csv(p_main)
    if p_hf is not None:
        backup_csv(p_hf)

    stats_e3 = enricheur.stats_l3(leads_l3)
    stats.etages_executes.append(
        StageStats(
            nom_etage="stage3_contacts",
            duree_secondes=duree,
            nb_appels_api=stats_e3.get("scrape_au_moins_un_email", 0),
            nb_succes=stats_e3.get("au_moins_un_email", 0),
            nb_echecs=stats_e3.get("total", 0) - stats_e3.get("au_moins_un_email", 0),
            cout_eur_estime=0.0,
            leads_collectes=len(leads_l3),
        )
    )

    nb_hors_filtre = sum(1 for lead in leads_l3 if lead.hors_filtre_entreprise)
    msg_hf = f" — Hors filtre entreprise (CSV séparé) : {nb_hors_filtre}" if nb_hors_filtre else ""
    console.print(
        f"\n[green]✓ Étage 3 : {len(leads_l3)} leads → {csv_path.name}[/green]\n"
        f"   Scraping réussi : {stats_e3.get('scrape_pct', 0)}% — "
        f"Au moins 1 email (scrapé ou pattern) : {stats_e3.get('au_moins_un_pct', 0)}% — "
        f"Patterns nominatifs : {stats_e3.get('dirigeant_pattern_pct', 0)}%"
        f"{msg_hf}"
    )

    if "html" in cfg.sortie.format:
        from .exporter_html import export_html_leads

        html_path = output_dir / "leads_qualifies.html"
        export_html_leads(csv_path, html_path, sous_titre=cfg.run.description or "")
        console.print(f"   📄 Rapport HTML leads : {html_path}")

    return leads_l3


def _executer_stage3_5(cfg, settings, leads_l3, output_dir, stats, dry_run: bool = False):
    """Exécute l'étage 3.5 (enrichissement Dropcontact).

    Si `dry_run=True`, on utilise `DropcontactClientDryRun` (zéro appel HTTP).
    """
    csv_path = output_dir / "etage3_5_enrichissement.csv"
    t0 = datetime.now(timezone.utc)

    def callback_save(leads_partial):
        export_stage3_5_csv(leads_partial, csv_path)

    if dry_run:
        console.print("[yellow]⚠  L3.5 en mode dry-run (aucun appel à Dropcontact).[/yellow]")
        client = DropcontactClientDryRun(
            cout_par_lead_eur=cfg.enrichissement_l3_5.cout_par_lead_eur,
        )
    else:
        budget = BudgetGuard(
            plafond_eur=max(0.01, cfg.budget.max_eur - stats.cout_total_eur)
        )
        limiter = RateLimiter(settings.max_requests_per_minute)
        api_key = settings.dropcontact_api_key.get_secret_value()
        client = DropcontactClient(
            DropcontactClientConfig(
                api_key=api_key,
                language=cfg.enrichissement_l3_5.language,
                siren=cfg.enrichissement_l3_5.siren,
                poll_initial_delay_s=cfg.enrichissement_l3_5.poll_initial_delay_s,
                poll_interval_s=cfg.enrichissement_l3_5.poll_interval_s,
                poll_timeout_s=cfg.enrichissement_l3_5.poll_timeout_s,
                cout_par_lead_eur=cfg.enrichissement_l3_5.cout_par_lead_eur,
                rate_limiter=limiter,
                budget=budget,
            )
        )

    cache_l35 = CacheStage35(output_dir / "cache_l3_5.sqlite")
    enricher = EnricheurStage35(
        client=client,
        config=cfg.enrichissement_l3_5,
        cache=cache_l35,
        callback_save_incremental=callback_save,
    )

    try:
        leads_l35 = enricher.enrichir(leads_l3)
    except BudgetExceededError as e:
        console.print(f"[red]✗ Budget L3.5 dépassé : {e}[/red]")
        leads_l35 = leads_l3  # On préserve les leads d'origine

    duree = (datetime.now(timezone.utc) - t0).total_seconds()
    export_stage3_5_csv(leads_l35, csv_path)
    backup_csv(csv_path)

    stats_e35 = enricher.stats_l35(leads_l35)
    stats.cout_total_eur += enricher.cout_total_eur
    stats.etages_executes.append(
        StageStats(
            nom_etage="stage3_5_enrichment",
            duree_secondes=duree,
            nb_appels_api=enricher.cache_misses,
            nb_succes=stats_e35.get("enrichis", 0),
            nb_echecs=stats_e35.get("erreurs", 0),
            cout_eur_estime=enricher.cout_total_eur,
            leads_collectes=len(leads_l35),
        )
    )

    console.print(
        f"\n[green]✓ Étage 3.5 : {len(leads_l35)} leads → {csv_path.name}[/green]\n"
        f"   Filtrés (hors filtre / inéligibles) : {stats_e35.get('filtres_out', 0)} — "
        f"Envoyés API : {stats_e35.get('envoyes_api', 0)} — "
        f"Enrichis : {stats_e35.get('enrichis', 0)} — "
        f"Erreurs : {stats_e35.get('erreurs', 0)} — "
        f"Ignorés (réseau) : {stats_e35.get('ignores_reseau', 0)}\n"
        f"   Email Dropcontact : {stats_e35.get('avec_email_pct', 0)}% — "
        f"Tel direct : {stats_e35.get('avec_phone_pct', 0)}% — "
        f"LinkedIn : {stats_e35.get('avec_linkedin_pct', 0)}% — "
        f"Coût : {enricher.cout_total_eur:.2f} €"
    )
    return leads_l35


def _executer_stage3_7(cfg, settings, leads_l3, output_dir, stats, dry_run: bool = False):
    """Exécute l'étage 3.7 (complétion : repêchage + enrichissement Societeinfo).

    Comble les champs de base manquants (SIREN, dirigeant, NAF, effectif, CA,
    emails, téléphone) via un provider externe, trace la provenance, et produit
    deux livrables : le CSV `etage3_7_completion.csv` + l'annexe `completion.md`.
    """
    csv_path = output_dir / "etage3_7_completion.csv"
    annexe_path = output_dir / "completion.md"
    t0 = datetime.now(timezone.utc)

    api_key = (
        settings.societeinfo_api_key.get_secret_value()
        if settings.has_societeinfo()
        else None
    )
    budget_eur = max(0.01, cfg.budget.max_eur - stats.cout_total_eur)
    provider = construire_provider_societeinfo(
        api_key=api_key,
        dry_run=dry_run,
        budget_eur=budget_eur,
        rate_per_min=settings.max_requests_per_minute,
    )
    if dry_run:
        console.print("[yellow]⚠  L3.7 en mode dry-run (aucun appel à Societeinfo).[/yellow]")

    etage = EtageCompletion(provider=provider)
    leads_l37 = etage.enrichir(leads_l3)

    duree = (datetime.now(timezone.utc) - t0).total_seconds()
    export_completion_csv(leads_l37, csv_path)
    backup_csv(csv_path)
    generer_annexe_completion(leads_l37, annexe_path)

    stats.cout_total_eur += etage.cout_total_eur
    stats.etages_executes.append(
        StageStats(
            nom_etage="completion",
            duree_secondes=duree,
            nb_appels_api=etage.nb_appeles,
            nb_succes=etage.nb_repeches,
            nb_echecs=etage.nb_appeles - etage.nb_repeches,
            cout_eur_estime=etage.cout_total_eur,
            leads_collectes=len(leads_l37),
        )
    )

    console.print(
        f"\n[green]✓ Étage 3.7 : {len(leads_l37)} leads → {csv_path.name}[/green]\n"
        f"   Appelés (provider) : {etage.nb_appeles} — "
        f"Repêchés : {etage.nb_repeches} — "
        f"Coût : {etage.cout_total_eur:.2f} €\n"
        f"   Annexe : {annexe_path.name}"
    )
    return leads_l37


def _filtrer_leads_a_scorer(leads, scorer_hors_filtre: bool):
    """Sélectionne les leads à envoyer à L4.

    Par défaut (scorer_hors_filtre=False) : seuls les qualifiés
    (hors_filtre_entreprise=False) — inutile de payer des tokens pour des leads
    déjà écartés. À True : tous les leads (diagnostic / calibration).
    """
    if scorer_hors_filtre:
        return list(leads)
    return [lead for lead in leads if not getattr(lead, "hors_filtre_entreprise", False)]


def _executer_stage4(cfg, settings, leads_l3, output_dir, stats, dry_run: bool = False):
    """Exécute l'étage 4 (scoring Claude + pitch).

    Si `dry_run=True`, on utilise un client factice (`ClaudeClientDryRun`)
    qui simule des scores sans appeler l'API. Permet de valider le flux
    bout-en-bout sans clé.
    """
    csv_path = output_dir / "etage4_prospection.csv"
    t0 = datetime.now(timezone.utc)

    def callback_save(leads_partial):
        export_stage4_csv(leads_partial, csv_path)

    if dry_run:
        console.print("[yellow]⚠  L4 en mode dry-run (aucun appel à Anthropic).[/yellow]")
        claude_client = ClaudeClientDryRun(
            modele=cfg.claude_scoring.modele,
            inclure_pitch=cfg.claude_scoring.inclure_pitch,
        )
    else:
        # Budget guard partagé avec le run global (récupère ce qui a été consommé)
        budget = BudgetGuard(
            plafond_eur=max(0.01, cfg.budget.max_eur - stats.cout_total_eur)
        )
        limiter = RateLimiter(settings.max_requests_per_minute)
        api_key = settings.anthropic_api_key.get_secret_value()
        claude_client = ClaudeClient(
            ClaudeClientConfig(
                api_key=api_key,
                modele=cfg.claude_scoring.modele,
                max_tokens_sortie=cfg.claude_scoring.max_tokens_sortie,
                rate_limiter=limiter,
                budget=budget,
            )
        )
    cache_l4 = CacheStage4(output_dir / "cache_l4.sqlite")
    enricher = EnricheurStage4(
        client=claude_client,
        config=cfg.claude_scoring,
        cache=cache_l4,
        callback_save_incremental=callback_save,
        emetteur=cfg.emetteur,
    )

    # Par défaut on ne score que les qualifiés (économie de tokens). Les leads
    # hors-filtre restent disponibles dans etage3_contacts_hors_filtre.csv.
    leads_a_scorer = _filtrer_leads_a_scorer(
        leads_l3, cfg.claude_scoring.scorer_hors_filtre
    )
    nb_skip = len(leads_l3) - len(leads_a_scorer)
    if nb_skip:
        console.print(
            f"[cyan]L4 : {nb_skip} leads hors-filtre ignorés "
            f"(scorer_hors_filtre=false) — {len(leads_a_scorer)} qualifiés à scorer.[/cyan]"
        )

    try:
        leads_l4 = enricher.enrichir(leads_a_scorer)
    except BudgetExceededError as e:
        console.print(f"[red]✗ Budget L4 dépassé : {e}[/red]")
        leads_l4 = []

    duree = (datetime.now(timezone.utc) - t0).total_seconds()
    export_stage4_csv(leads_l4, csv_path)
    backup_csv(csv_path)

    if "html" in cfg.sortie.format:
        from .exporter_html import export_html_emails

        html_path = output_dir / "emails_prospection.html"
        export_html_emails(csv_path, html_path, sous_titre=cfg.run.description or "")
        console.print(f"   📄 Rapport HTML emails : {html_path}")

    stats_e4 = enricher.stats_l4(leads_l4)
    stats.cout_total_eur += enricher.cout_total_eur
    stats.etages_executes.append(
        StageStats(
            nom_etage="stage4_prospection",
            duree_secondes=duree,
            nb_appels_api=enricher.cache_misses,
            nb_succes=stats_e4.get("scored", 0),
            nb_echecs=stats_e4.get("erreurs", 0),
            cout_eur_estime=enricher.cout_total_eur,
            leads_collectes=len(leads_l4),
        )
    )

    console.print(
        f"\n[green]✓ Étage 4 : {len(leads_l4)} leads → {csv_path.name}[/green]\n"
        f"   Top leads (score ≥ {cfg.claude_scoring.seuil_top_lead}) : "
        f"{stats_e4.get('top_leads', 0)} ({stats_e4.get('top_pct', 0)}%) — "
        f"Score moyen : {stats_e4.get('score_moyen', 0)} — "
        f"Coût : {enricher.cout_total_eur:.4f} € — "
        f"Cache : {enricher.cache_hits} hits / {enricher.cache_misses} miss"
    )
    return leads_l4


# ════════════════════════════════════════════════════════════════
# Orchestrateur
# ════════════════════════════════════════════════════════════════


@dataclass
class OrchestrationResult:
    """Résultat du séquençage : leads par niveau + métadonnées de finalisation."""

    leads_l1: list[Any] | None = None
    leads_l2: list[Any] | None = None
    leads_l3: list[Any] | None = None
    leads_l35: list[Any] | None = None
    leads_l37: list[Any] | None = None
    leads_l4: list[Any] | None = None
    nb_leads_finaux: int = 0
    sources_rgpd: list[str] = field(default_factory=list)

    @property
    def leads_finaux(self) -> list[Any]:
        """Le niveau le plus avancé non nul (L4 > L3.7 > L3.5 > L3 > L2 > L1)."""
        for lst in (
            self.leads_l4,
            self.leads_l37,
            self.leads_l35,
            self.leads_l3,
            self.leads_l2,
            self.leads_l1,
        ):
            if lst is not None:
                return lst
        return []


def _qualifies(leads: list[Any] | None) -> int:
    """Nombre de leads passant les filtres entreprise (hors_filtre=False)."""
    if not leads:
        return 0
    return sum(1 for lead in leads if not getattr(lead, "hors_filtre_entreprise", False))


def executer_pipeline(
    cfg,
    settings,
    stages_demandes: list[float | int],
    output_dir: Path,
    stats: RunStats,
    *,
    from_csv_path: Path | None = None,
    l2_provider: str = "datagouv",
    dry_run: bool = False,
    cache: SessionCache | None = None,
    logger: Logger | None = None,
    emit: EmitFn | None = None,
) -> OrchestrationResult:
    """Exécute la séquence d'étages demandée (L0→L4) et renvoie les leads.

    Source de vérité unique du séquençage, partagée par la CLI et le worker.
    `stats` est mutée par les étages (coûts, StageStats). `emit`, s'il est
    fourni, signale la progression (étape lisible, 0-100, counts) en début/fin
    d'étage — sans coupler l'orchestrateur à Supabase.
    """
    logger = logger or getLogger("renoboost.orchestrateur")
    cache = cache or SessionCache(output_dir / "cache.sqlite")

    def _emit(etape: str, progress: int, res: OrchestrationResult, leads_final: int = 0) -> None:
        if emit is None:
            return
        decouverte = len(res.leads_l1) if res.leads_l1 is not None else (
            len(res.leads_l2) if res.leads_l2 is not None else 0
        )
        emit(
            etape,
            progress,
            {
                "decouverte": decouverte,
                "qualifies": _qualifies(res.leads_l2 or res.leads_l1),
                "leads": leads_final,
            },
        )

    res = OrchestrationResult()
    sources_rgpd = res.sources_rgpd

    # ─── Étage 0 — Découverte SIRENE-first (alternative à 1+2) ───
    stage0_a_tourne = False
    if 0 in stages_demandes:
        res.leads_l2 = _executer_stage0(
            cfg=cfg,
            settings=settings,
            output_dir=output_dir,
            stats=stats,
            enrichir_avec_places=(1 in stages_demandes),
            dry_run=dry_run,
        )
        stage0_a_tourne = True
        sources_rgpd.append(
            "API recherche-entreprises.api.gouv.fr — découverte SIRENE-first (open data)"
        )
        if 1 in stages_demandes:
            sources_rgpd.append(
                "Google Places API (New) — enrichissement ciblé par nom + ville"
            )
        _emit("Découverte (SIRENE)", 40, res)

    # ─── Étage 1 (mode Places-first uniquement, exclusif de stage 0) ───
    if 1 in stages_demandes and not stage0_a_tourne and cfg.stages.enable_stage_1_decouverte:
        res.leads_l1 = _executer_stage1(
            cfg=cfg,
            settings=settings,
            cache=cache,
            output_dir=output_dir,
            stats=stats,
            dry_run=dry_run,
        )
        sources_rgpd.append("Google Places API (New) — données publiques")
        _emit("Découverte (Google Places)", 20, res)

    # ─── Étage 2 ───
    if 2 in stages_demandes and stage0_a_tourne:
        logger.info("Stage 2 demandé mais déjà couvert par stage 0 (SIRENE-first) — skip")
    elif 2 in stages_demandes:
        # Charger L1 depuis le CSV si pas déjà en mémoire
        if res.leads_l1 is None:
            csv_l1 = from_csv_path or (output_dir / "etage1_decouverte.csv")
            if not csv_l1.exists():
                console.print(
                    f"[red]✗ Impossible de lancer L2 : CSV L1 introuvable ({csv_l1}).[/red]"
                )
                sys.exit(2)
            res.leads_l1 = lire_stage1_csv(csv_l1)
            logger.info("L1 chargé depuis CSV existant : %d leads", len(res.leads_l1))

        res.leads_l2 = _executer_stage2(
            cfg=cfg,
            settings=settings,
            leads_l1=res.leads_l1,
            cache=cache,
            output_dir=output_dir,
            stats=stats,
            l2_provider=l2_provider,
            dry_run=dry_run,
        )
        if l2_provider == "societeinfo":
            sources_rgpd.append(
                "Societeinfo API — appariement SIREN (registres officiels FR)"
            )
        else:
            sources_rgpd.append(
                "API recherche-entreprises.api.gouv.fr — registre du commerce (open data)"
            )
        _emit("Qualification entreprises", 40, res)

    # ─── Étage 3 ───
    if 3 in stages_demandes:
        if res.leads_l2 is None:
            # Charger L2 depuis le CSV
            csv_l2 = output_dir / "etage2_entreprises.csv"
            if not csv_l2.exists():
                console.print(
                    f"[red]✗ Impossible de lancer L3 : CSV L2 introuvable ({csv_l2}).[/red]\n"
                    "   Lance d'abord --stages 2."
                )
                sys.exit(2)
            res.leads_l2 = lire_stage2_csv(csv_l2)
            logger.info("L2 chargé depuis CSV existant : %d leads", len(res.leads_l2))

        res.leads_l3 = _executer_stage3(
            cfg=cfg,
            leads_l2=res.leads_l2,
            cache=cache,
            output_dir=output_dir,
            stats=stats,
        )
        sources_rgpd.append(
            "Mentions légales / pages contact des sites web (LCEN — données publiques)"
        )
        sources_rgpd.append("Génération de patterns d'emails (logique algorithmique)")
        _emit("Contacts (scraping/patterns)", 60, res)

    # ─── Étage 3.5 (enrichissement Dropcontact, optionnel) ───
    if 3.5 in stages_demandes:
        if res.leads_l3 is None:
            # Charger L3 depuis le CSV
            csv_l3 = output_dir / "etage3_contacts.csv"
            if not csv_l3.exists():
                console.print(
                    f"[red]✗ Impossible de lancer L3.5 : CSV L3 introuvable ({csv_l3}).[/red]\n"
                    "   Lance d'abord --stages 3."
                )
                sys.exit(2)
            res.leads_l3 = lire_stage3_csv(csv_l3)
            logger.info("L3 chargé depuis CSV existant : %d leads", len(res.leads_l3))

        if not dry_run and not settings.has_dropcontact():
            console.print(
                "[red]✗ DROPCONTACT_API_KEY manquante.[/red] "
                "Ajoute-la dans .env, ou relance avec --dry-run pour simuler L3.5."
            )
            sys.exit(2)

        res.leads_l35 = _executer_stage3_5(
            cfg=cfg,
            settings=settings,
            leads_l3=res.leads_l3,
            output_dir=output_dir,
            stats=stats,
            dry_run=dry_run,
        )
        if dry_run:
            sources_rgpd.append(
                "Étage 3.5 simulé (dry-run) — aucune donnée envoyée à Dropcontact"
            )
        else:
            sources_rgpd.append(
                "Dropcontact API — enrichissement contacts B2B "
                "(sous-traitant RGPD — voir RGPD_COMPLIANCE.md)"
            )
        _emit("Enrichissement contacts", 75, res)

    # ─── Étage 3.7 (complétion : repêchage + enrichissement, optionnel) ───
    if 3.7 in stages_demandes:
        # Source : L3.5 si dispo, sinon L3, sinon CSV sur disque.
        leads_pour_l37 = res.leads_l35 if res.leads_l35 is not None else res.leads_l3
        if leads_pour_l37 is None:
            csv_l35 = output_dir / "etage3_5_enrichissement.csv"
            csv_l3 = output_dir / "etage3_contacts.csv"
            if csv_l35.exists():
                leads_pour_l37 = lire_stage3_5_csv(csv_l35)
                logger.info("L3.5 chargé depuis CSV existant : %d leads", len(leads_pour_l37))
            elif csv_l3.exists():
                leads_pour_l37 = lire_stage3_csv(csv_l3)
                logger.info("L3 chargé depuis CSV existant : %d leads", len(leads_pour_l37))
            else:
                console.print(
                    f"[red]✗ Impossible de lancer L3.7 : CSV L3 introuvable ({csv_l3}).[/red]\n"
                    "   Lance d'abord --stages 3."
                )
                sys.exit(2)

        use_dry_37 = dry_run or not settings.has_societeinfo()
        if use_dry_37 and not dry_run:
            console.print(
                "[yellow]⚠  SOCIETEINFO_API_KEY absente → L3.7 en dry-run "
                "(données simulées).[/yellow]"
            )

        res.leads_l37 = _executer_stage3_7(
            cfg=cfg,
            settings=settings,
            leads_l3=leads_pour_l37,
            output_dir=output_dir,
            stats=stats,
            dry_run=use_dry_37,
        )
        if use_dry_37:
            sources_rgpd.append(
                "Étage 3.7 simulé (dry-run) — aucune donnée envoyée à Societeinfo"
            )
        else:
            sources_rgpd.append(
                "Societeinfo API — complétion firmographique "
                "(registres officiels FR — voir RGPD_COMPLIANCE.md)"
            )
        _emit("Complétion firmographique", 80, res)

    # ─── Étage 4 ───
    if 4 in stages_demandes:
        # Source : complétion 3.7 si on l'a, sinon L3.5, sinon L3.
        leads_pour_l4 = (
            res.leads_l37
            if res.leads_l37 is not None
            else res.leads_l35
            if res.leads_l35 is not None
            else res.leads_l3
        )
        if leads_pour_l4 is None:
            # Si un CSV L3.5 existe sur disque, on le préfère (pas perdre l'enrichissement)
            csv_l35 = output_dir / "etage3_5_enrichissement.csv"
            csv_l3 = output_dir / "etage3_contacts.csv"
            if csv_l35.exists():
                leads_pour_l4 = lire_stage3_5_csv(csv_l35)
                logger.info("L3.5 chargé depuis CSV existant : %d leads", len(leads_pour_l4))
            elif csv_l3.exists():
                leads_pour_l4 = lire_stage3_csv(csv_l3)
                logger.info("L3 chargé depuis CSV existant : %d leads", len(leads_pour_l4))
            else:
                console.print(
                    f"[red]✗ Impossible de lancer L4 : CSV L3 introuvable ({csv_l3}).[/red]\n"
                    "   Lance d'abord --stages 3."
                )
                sys.exit(2)
        res.leads_l3 = leads_pour_l4  # alias pour la suite (legacy)

        if not dry_run and not settings.has_anthropic():
            console.print(
                "[red]✗ ANTHROPIC_API_KEY manquante.[/red] "
                "Ajoute-la dans .env, ou relance avec --dry-run pour simuler L4."
            )
            sys.exit(2)

        res.leads_l4 = _executer_stage4(
            cfg=cfg,
            settings=settings,
            leads_l3=res.leads_l3,
            output_dir=output_dir,
            stats=stats,
            dry_run=dry_run,
        )
        if dry_run:
            sources_rgpd.append(
                "Étage 4 simulé (dry-run) — aucune donnée envoyée à Anthropic"
            )
        else:
            sources_rgpd.append(
                "Anthropic Claude API — scoring qualitatif "
                "(sous-traitant — voir RGPD_COMPLIANCE.md)"
            )
        _emit("Rédaction des e-mails", 95, res, leads_final=len(res.leads_l4))

    res.nb_leads_finaux = len(res.leads_finaux)
    return res
