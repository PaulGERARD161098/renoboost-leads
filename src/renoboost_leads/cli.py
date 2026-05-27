"""CLI principale — point d'entrée `python -m renoboost_leads.cli ...`."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import click
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from .cli_rgpd import cleanup as rgpd_cleanup
from .cli_rgpd import forget as rgpd_forget
from .common.budget_guard import BudgetExceededError, BudgetGuard
from .common.cache import SessionCache
from .common.logger import setup_logger
from .common.rate_limiter import RateLimiter
from .config_loader import load_campaign_config
from .exporter import (
    backup_csv,
    export_csv_crm,
    export_run_stats,
    export_stage1_csv,
    export_stage2_csv,
    export_stage3_5_csv,
    export_stage3_csv,
    export_stage3_csv_separe_hors_filtre,
    export_stage4_csv,
    generer_registre_rgpd,
    lire_stage1_csv,
    lire_stage2_csv,
    lire_stage3_5_csv,
    lire_stage3_csv,
    lire_stage4_csv,
)
from .models import CampaignConfig, RunStats, StageStats
from .settings import PROJECT_ROOT, get_settings
from .stage1_decouverte.extractor import ExtracteurStage1
from .stage1_decouverte.geo_grid import grille_pour_zone
from .stage1_decouverte.places_client import (
    COUT_TEXT_SEARCH_EUR,
    PlacesClient,
    PlacesClientConfig,
)
from .stage2_entreprises.enricher import EnricheurStage2
from .stage2_entreprises.pappers_client import PappersClient, PappersClientConfig
from .stage2_entreprises.recherche_client import (
    RechercheClientConfig,
    RechercheEntreprisesClient,
)
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
from .veille_immatriculations.cli_veille import veille_group

console = Console()


# ════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════


def _build_session_id(client_name: str) -> str:
    return f"{datetime.now().strftime('%Y-%m-%d_%H%M')}_{client_name}"


def _load_config_or_exit(config_path: Path) -> CampaignConfig:
    try:
        return load_campaign_config(config_path)
    except FileNotFoundError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(2)
    except ValidationError as e:
        console.print(f"[red]✗ Config YAML invalide :[/red]\n{e}")
        sys.exit(2)


def _check_google_key_or_exit() -> str:
    settings = get_settings()
    if not settings.has_google_places():
        console.print(
            "[red]✗ GOOGLE_PLACES_API_KEY manquante.[/red] "
            "Crée un fichier .env (cf. .env.example) et colle ta clé."
        )
        sys.exit(2)
    return settings.google_places_api_key.get_secret_value()


def _trouver_dossier_existant(client_name: str) -> Path | None:
    """Cherche le dernier dossier de sortie existant pour ce client.

    BUG B2 fix : matching tolerant (case-insensitive, accents, espaces vs underscores).
    """
    import unicodedata

    base = PROJECT_ROOT / "data" / "output"
    if not base.exists():
        return None

    def _normalize(s: str) -> str:
        nfkd = unicodedata.normalize("NFKD", s)
        ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
        return ascii_only.lower().replace(" ", "_").replace("-", "_")

    cible = _normalize(client_name)
    candidats = sorted(
        [d for d in base.iterdir() if d.is_dir() and _normalize(d.name).endswith(cible)],
        reverse=True,
    )
    return candidats[0] if candidats else None


# ════════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════════


@click.group()
def cli() -> None:
    """RénoBoost Leads — outil de prospection B2B paramétrable."""


# ─── check-connections ───
@cli.command(name="check-connections")
def check_connections() -> None:
    """Teste les connexions aux APIs."""
    settings = get_settings()

    table = Table(title="État des connexions APIs")
    table.add_column("API", style="bold")
    table.add_column("Configuré", justify="center")
    table.add_column("Test", justify="center")
    table.add_column("Détail")

    # Google Places (étage 1) — clé requise
    if settings.has_google_places():
        try:
            limiter = RateLimiter(settings.max_requests_per_minute)
            budget = BudgetGuard(plafond_eur=1.0)
            client = PlacesClient(
                PlacesClientConfig(
                    api_key=settings.google_places_api_key.get_secret_value(),
                    rate_limiter=limiter,
                    budget=budget,
                )
            )
            ok, msg = client.health_check()
            statut = "[green]✓[/green]" if ok else "[red]✗[/red]"
            table.add_row("Google Places (étage 1)", "✓", statut, msg[:60])
        except Exception as e:  # noqa: BLE001
            table.add_row("Google Places (étage 1)", "✓", "[red]✗[/red]", str(e)[:60])
    else:
        table.add_row("Google Places (étage 1)", "[red]✗[/red]", "—", "Clé absente dans .env")

    # API Recherche d'entreprises (étage 2) — sans auth
    try:
        limiter = RateLimiter(60)
        rech_client = RechercheEntreprisesClient(RechercheClientConfig(rate_limiter=limiter))
        ok, msg = rech_client.health_check()
        statut = "[green]✓[/green]" if ok else "[red]✗[/red]"
        table.add_row(
            "API recherche-entreprises.api.gouv.fr (étage 2)",
            "[green]✓[/green]",
            statut,
            msg[:60],
        )
    except Exception as e:  # noqa: BLE001
        table.add_row(
            "API recherche-entreprises.api.gouv.fr (étage 2)",
            "[green]✓[/green]",
            "[red]✗[/red]",
            str(e)[:60],
        )

    # Étage 3 — pas d'auth, pas de test (le scraping dépend du site cible)
    table.add_row(
        "Scraping web (étage 3)",
        "[green]✓[/green]",
        "[dim]autonome[/dim]",
        "Module de scraping opérationnel (testé site par site)",
    )

    # Anthropic (étage 4)
    if settings.has_anthropic():
        table.add_row(
            "Anthropic Claude (étage 4)",
            "[green]✓[/green]",
            "[dim]clé présente[/dim]",
            f"Modèle par défaut config : {settings.claude_model}",
        )
    else:
        table.add_row(
            "Anthropic Claude (étage 4)",
            "[yellow]—[/yellow]",
            "—",
            "Clé absente (requise pour --stages 4)",
        )

    console.print(table)


# ─── estimate ───
@cli.command()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
def estimate(config_path: Path) -> None:
    """Estime le coût et le volume d'un run AVANT lancement (zéro appel API)."""
    cfg = _load_config_or_exit(config_path)

    points = grille_pour_zone(cfg.zone)
    nb_secteurs = len(cfg.secteurs)
    nb_recherches_max = len(points) * nb_secteurs
    cout_etage1_max = nb_recherches_max * COUT_TEXT_SEARCH_EUR
    nb_recherches_realiste = min(nb_recherches_max, max(15, cfg.volume.cible // 10))
    cout_etage1_realiste = nb_recherches_realiste * COUT_TEXT_SEARCH_EUR

    table = Table(title=f"Estimation — {cfg.run.client_name}")
    table.add_column("Élément", style="bold")
    table.add_column("Valeur", justify="right")

    table.add_row("Points GPS de la grille", f"{len(points)}")
    table.add_row("Secteurs ciblés", f"{nb_secteurs}")
    table.add_row("Volume cible", f"{cfg.volume.cible} leads")
    table.add_row("Plafond budget config", f"{cfg.budget.max_eur:.2f} €")
    table.add_row("", "")
    table.add_row("Recherches Places max théorique", f"{nb_recherches_max}")
    table.add_row("Coût étage 1 max théorique", f"{cout_etage1_max:.2f} €")
    table.add_row(
        "[bold]Coût étage 1 estimé réaliste[/bold]",
        f"[bold]{cout_etage1_realiste:.2f} €[/bold]",
    )
    table.add_row("", "")
    table.add_row("[green]Coût étage 2 (data.gouv.fr)[/green]", "[green]0,00 € (gratuit)[/green]")
    table.add_row("[green]Coût étage 3 (scraping)[/green]", "[green]0,00 € (gratuit)[/green]")

    if cfg.stages.enable_stage_4_prospection:
        # Tarif indicatif : Haiku ~0.005 €/lead, Sonnet ~0.02 €/lead
        cout_par_lead = 0.005 if cfg.claude_scoring.modele == "claude-haiku-4-5" else 0.02
        cout_e4 = cfg.volume.cible * cout_par_lead
        table.add_row(
            f"Coût étage 4 ({cfg.claude_scoring.modele})",
            f"~{cout_e4:.2f} €",
        )

    console.print(table)


# ─── run ───
@cli.command()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option(
    "--stages",
    default="1",
    help="Étages à exécuter, séparés par virgule. Ex: '1', '2', '1,2,3', '2,3'.",
)
@click.option(
    "--from-csv",
    "from_csv_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Pour étages 2/3 : repartir d'un CSV existant au lieu de relancer L1.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Simulation : ne fait aucun appel API payant, retourne des leads factices.",
)
def run(config_path: Path, stages: str, from_csv_path: Path | None, dry_run: bool) -> None:
    """Lance un run de prospection."""
    cfg = _load_config_or_exit(config_path)

    # Parse les étages demandés (accepte int "1/2/3/4" et float "3.5")
    try:
        stages_demandes = sorted(
            {
                float(s.strip()) if "." in s else int(s.strip())
                for s in stages.split(",")
                if s.strip()
            }
        )
    except ValueError:
        console.print(f"[red]✗ Format --stages invalide : '{stages}'.[/red]")
        sys.exit(2)

    if any(s not in (1, 2, 3, 3.5, 4) for s in stages_demandes):
        console.print(
            "[yellow]⚠  Étages valides : 1, 2, 3, 3.5, 4. Étages inconnus ignorés.[/yellow]"
        )
        stages_demandes = [s for s in stages_demandes if s in (1, 2, 3, 3.5, 4)]

    if not stages_demandes:
        console.print("[red]✗ Aucun étage valide demandé.[/red]")
        sys.exit(2)

    # ─── Résolution du dossier de sortie ───
    if from_csv_path:
        # On reprend dans le dossier du CSV existant
        output_dir = from_csv_path.parent
        session_id = output_dir.name
        console.print(f"[cyan]Mode reprise depuis : {from_csv_path}[/cyan]")
    elif 1 not in stages_demandes:
        # On veut juste L2/L3 — on cherche le dernier dossier avec un CSV L1 pour ce client
        existant = _trouver_dossier_existant(cfg.run.client_name)
        if existant is None or not (existant / "etage1_decouverte.csv").exists():
            console.print(
                f"[red]✗ Pour lancer L2/L3 sans L1, il faut un CSV L1 existant.[/red]\n"
                f"   Aucun trouvé pour client_name='{cfg.run.client_name}'.\n"
                f"   Solutions :\n"
                f"   1. Lance d'abord L1 : --stages 1\n"
                f"   2. Ou indique le CSV : --from-csv data/output/<dossier>/etage1_decouverte.csv"
            )
            sys.exit(2)
        output_dir = existant
        session_id = output_dir.name
        console.print(f"[cyan]Reprise du dossier existant : {output_dir.name}[/cyan]")
    else:
        # Nouveau run avec L1
        session_id = _build_session_id(cfg.run.client_name)
        output_dir = PROJECT_ROOT / "data" / "output" / session_id
        output_dir.mkdir(parents=True, exist_ok=True)
        # Snapshot du config utilisé pour traçabilité + rapport
        try:
            import shutil
            shutil.copy2(config_path, output_dir / "config_snapshot.yaml")
        except OSError:
            pass

    # Logger
    logger = setup_logger(output_dir=output_dir, level=get_settings().log_level)
    logger.info("─" * 60)
    logger.info("Run %s (config: %s)", session_id, config_path)
    logger.info("Stages demandés : %s", stages_demandes)

    # Stats du run
    stats = RunStats(
        session_id=session_id,
        campaign=cfg.run.client_name,
        debut=datetime.now(timezone.utc),
    )

    settings = get_settings()
    cache = SessionCache(output_dir / "cache.sqlite")
    sources_rgpd: list[str] = []

    # ─── Étage 1 ───
    leads_l1 = None
    if 1 in stages_demandes and cfg.stages.enable_stage_1_decouverte:
        leads_l1 = _executer_stage1(
            cfg=cfg,
            settings=settings,
            cache=cache,
            output_dir=output_dir,
            stats=stats,
            dry_run=dry_run,
        )
        sources_rgpd.append("Google Places API (New) — données publiques")

    # ─── Étage 2 ───
    leads_l2 = None
    if 2 in stages_demandes:
        # Charger L1 depuis le CSV si pas déjà en mémoire
        if leads_l1 is None:
            csv_l1 = from_csv_path or (output_dir / "etage1_decouverte.csv")
            if not csv_l1.exists():
                console.print(
                    f"[red]✗ Impossible de lancer L2 : CSV L1 introuvable ({csv_l1}).[/red]"
                )
                sys.exit(2)
            leads_l1 = lire_stage1_csv(csv_l1)
            logger.info("L1 chargé depuis CSV existant : %d leads", len(leads_l1))

        leads_l2 = _executer_stage2(
            cfg=cfg,
            settings=settings,
            leads_l1=leads_l1,
            cache=cache,
            output_dir=output_dir,
            stats=stats,
        )
        sources_rgpd.append(
            "API recherche-entreprises.api.gouv.fr — registre du commerce (open data)"
        )

    # ─── Étage 3 ───
    leads_l3 = None
    if 3 in stages_demandes:
        if leads_l2 is None:
            # Charger L2 depuis le CSV
            csv_l2 = output_dir / "etage2_entreprises.csv"
            if not csv_l2.exists():
                console.print(
                    f"[red]✗ Impossible de lancer L3 : CSV L2 introuvable ({csv_l2}).[/red]\n"
                    "   Lance d'abord --stages 2."
                )
                sys.exit(2)
            leads_l2 = lire_stage2_csv(csv_l2)
            logger.info("L2 chargé depuis CSV existant : %d leads", len(leads_l2))

        leads_l3 = _executer_stage3(
            cfg=cfg,
            leads_l2=leads_l2,
            cache=cache,
            output_dir=output_dir,
            stats=stats,
        )
        sources_rgpd.append(
            "Mentions légales / pages contact des sites web (LCEN — données publiques)"
        )
        sources_rgpd.append("Génération de patterns d'emails (logique algorithmique)")

    # ─── Étage 3.5 (enrichissement Dropcontact, optionnel) ───
    leads_l35 = None
    if 3.5 in stages_demandes:
        if leads_l3 is None:
            # Charger L3 depuis le CSV
            csv_l3 = output_dir / "etage3_contacts.csv"
            if not csv_l3.exists():
                console.print(
                    f"[red]✗ Impossible de lancer L3.5 : CSV L3 introuvable ({csv_l3}).[/red]\n"
                    "   Lance d'abord --stages 3."
                )
                sys.exit(2)
            leads_l3 = lire_stage3_csv(csv_l3)
            logger.info("L3 chargé depuis CSV existant : %d leads", len(leads_l3))

        if not dry_run and not settings.has_dropcontact():
            console.print(
                "[red]✗ DROPCONTACT_API_KEY manquante.[/red] "
                "Ajoute-la dans .env, ou relance avec --dry-run pour simuler L3.5."
            )
            sys.exit(2)

        leads_l35 = _executer_stage3_5(
            cfg=cfg,
            settings=settings,
            leads_l3=leads_l3,
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

    # ─── Étage 4 ───
    leads_l4 = None
    if 4 in stages_demandes:
        # Source L3.5 prioritaire si on l'a, sinon L3 (avec ou sans depuis CSV).
        leads_pour_l4 = leads_l35 if leads_l35 is not None else leads_l3
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
        leads_l3 = leads_pour_l4  # alias pour la suite (legacy)

        if not dry_run and not settings.has_anthropic():
            console.print(
                "[red]✗ ANTHROPIC_API_KEY manquante.[/red] "
                "Ajoute-la dans .env, ou relance avec --dry-run pour simuler L4."
            )
            sys.exit(2)

        leads_l4 = _executer_stage4(
            cfg=cfg,
            settings=settings,
            leads_l3=leads_l3,
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

    # ─── Finalisation : registre RGPD + stats ───
    nb_leads_finaux = (
        len(leads_l4)
        if leads_l4 is not None
        else len(leads_l35)
        if leads_l35 is not None
        else len(leads_l3)
        if leads_l3 is not None
        else len(leads_l2)
        if leads_l2 is not None
        else len(leads_l1)
        if leads_l1 is not None
        else 0
    )
    stats.leads_finaux = nb_leads_finaux
    stats.fin = datetime.now(timezone.utc)
    stats.duree_totale_secondes = (stats.fin - stats.debut).total_seconds()
    export_run_stats(stats, output_dir / "run_stats.json")

    # ─── Persistance optionnelle (Supabase Storage) ───
    # Si STORAGE_BACKEND=supabase, on uploade la session au remote pour
    # qu'elle survive aux redéploiements Streamlit Cloud. En mode local
    # (défaut), c'est un no-op silencieux.
    if settings.storage_backend == "supabase":
        try:
            from .storage import get_storage

            storage = get_storage()
            res_upload = storage.upload_session(session_id)
            if res_upload.get("ok"):
                console.print(
                    f"[cyan]☁  Session synchronisée vers Supabase "
                    f"({res_upload.get('bytes_uploaded', 0) // 1024} KB)[/cyan]"
                )
            else:
                console.print(
                    f"[yellow]⚠  Upload Supabase échoué : "
                    f"{res_upload.get('error', 'inconnu')}[/yellow]"
                )
        except Exception as e:  # noqa: BLE001 — on ne fait pas planter le run
            console.print(
                f"[yellow]⚠  Storage Supabase indisponible : {e}[/yellow]"
            )

    generer_registre_rgpd(
        output_path=output_dir / "registre_rgpd.md",
        client_name=cfg.run.client_name,
        nb_leads=nb_leads_finaux,
        sources=sources_rgpd or ["Aucune source utilisée"],
        etages_executes=stages_demandes,
    )

    console.print(f"\n[bold]Sortie complète :[/bold] {output_dir}")


# ════════════════════════════════════════════════════════════════
# Sous-fonctions par étage (pour clarté)
# ════════════════════════════════════════════════════════════════


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


def _executer_stage2(cfg, settings, leads_l1, cache, output_dir, stats):
    """Exécute l'étage 2."""
    csv_path = output_dir / "etage2_entreprises.csv"
    t0 = datetime.now(timezone.utc)

    def callback_save(leads_partial):
        export_stage2_csv(leads_partial, csv_path)

    limiter = RateLimiter(60)  # 60 req/min, largement sous la limite de 7 req/s
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

    scraper = ScraperContact(rate_limit_seconds=1.0)
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
        f"Erreurs : {stats_e35.get('erreurs', 0)}\n"
        f"   Email Dropcontact : {stats_e35.get('avec_email_pct', 0)}% — "
        f"Tel direct : {stats_e35.get('avec_phone_pct', 0)}% — "
        f"LinkedIn : {stats_e35.get('avec_linkedin_pct', 0)}% — "
        f"Coût : {enricher.cout_total_eur:.2f} €"
    )
    return leads_l35


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


# ─── resume ───
@cli.command()
@click.option(
    "--session-id",
    "session_id",
    required=True,
    help="ID de la session à reprendre (nom du dossier dans data/output/).",
)
@click.option(
    "--stages",
    default="2,3",
    help="Étages à exécuter sur les leads existants.",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Config YAML (pour récupérer client_name, etc.).",
)
def resume(session_id: str, stages: str, config_path: Path) -> None:
    """Reprend un run interrompu en partant des CSV existants."""
    output_dir = PROJECT_ROOT / "data" / "output" / session_id
    if not output_dir.exists():
        console.print(f"[red]✗ Dossier de session introuvable : {output_dir}[/red]")
        sys.exit(2)

    csv_l1 = output_dir / "etage1_decouverte.csv"
    if not csv_l1.exists():
        console.print(f"[red]✗ CSV étage 1 manquant dans la session : {csv_l1}[/red]")
        sys.exit(2)

    # On délègue à `run` avec le bon CSV
    ctx = click.Context(run)
    ctx.invoke(
        run,
        config_path=config_path,
        stages=stages,
        from_csv_path=csv_l1,
        dry_run=False,
    )


# ─── export ───
@cli.command()
@click.option(
    "--session-id",
    "session_id",
    required=True,
    help="ID de la session à exporter (nom du dossier dans data/output/).",
)
@click.option(
    "--source",
    type=click.Choice(["auto", "l4", "l3.5", "l3"]),
    default="auto",
    help="CSV source à utiliser. 'auto' choisit le plus avancé disponible.",
)
@click.option(
    "--top-only",
    is_flag=True,
    help="N'exporter que les leads `top_lead=True` (utile après L4).",
)
@click.option(
    "--avec-email-uniquement",
    is_flag=True,
    help="N'exporter que les leads avec au moins un email (vérifié, pattern, ou Dropcontact).",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Chemin du CSV exportable. Défaut : <session>/leads_exportables.csv.",
)
def export(
    session_id: str,
    source: str,
    top_only: bool,
    avec_email_uniquement: bool,
    output_path: Path | None,
) -> None:
    """Génère un CSV exportable (colonnes utiles pour démarchage / import CRM)."""
    output_dir = PROJECT_ROOT / "data" / "output" / session_id
    if not output_dir.exists():
        console.print(f"[red]✗ Session introuvable : {output_dir}[/red]")
        sys.exit(2)

    csv_l4 = output_dir / "etage4_prospection.csv"
    csv_l35 = output_dir / "etage3_5_enrichissement.csv"
    csv_l3 = output_dir / "etage3_contacts.csv"

    if source == "auto":
        if csv_l4.exists():
            chosen, loader = csv_l4, lire_stage4_csv
        elif csv_l35.exists():
            chosen, loader = csv_l35, lire_stage3_5_csv
        elif csv_l3.exists():
            chosen, loader = csv_l3, lire_stage3_csv
        else:
            console.print(f"[red]✗ Aucun CSV exploitable dans {output_dir}.[/red]")
            sys.exit(2)
    elif source == "l4":
        chosen, loader = csv_l4, lire_stage4_csv
    elif source == "l3.5":
        chosen, loader = csv_l35, lire_stage3_5_csv
    else:  # l3
        chosen, loader = csv_l3, lire_stage3_csv

    if not chosen.exists():
        console.print(f"[red]✗ CSV source introuvable : {chosen}[/red]")
        sys.exit(2)

    leads = loader(chosen)
    nb_total = len(leads)

    if top_only:
        leads = [lead for lead in leads if getattr(lead, "top_lead", False)]
    if avec_email_uniquement:
        leads = [
            lead
            for lead in leads
            if getattr(lead, "email_dropcontact", None)
            or getattr(lead, "emails_verifies", None)
            or getattr(lead, "emails_candidats", None)
        ]

    if output_path is None:
        suffix_parts = []
        if top_only:
            suffix_parts.append("top")
        if avec_email_uniquement:
            suffix_parts.append("avec_email")
        suffix = "_" + "_".join(suffix_parts) if suffix_parts else ""
        output_path = output_dir / f"leads_exportables{suffix}.csv"

    p = export_csv_crm(leads, output_path)
    console.print(
        f"[green]✓ Export généré : {p}[/green]\n"
        f"   Source : {chosen.name} — Leads : {len(leads)} / {nb_total} "
        f"({'top_only' if top_only else 'tous'}"
        f"{', avec email' if avec_email_uniquement else ''})"
    )


def _format_octets(n: int) -> str:
    for unit in ("o", "Ko", "Mo", "Go"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} To"


@cli.command(name="forget")
@click.option("--email", default=None, help="Email à effacer (multi-colonnes).")
@click.option("--siren", default=None, help="SIREN à effacer.")
@click.option("--place-id", default=None, help="place_id Google à effacer.")
@click.option("--motif", default="demande RGPD", help="Motif inscrit au registre.")
@click.option(
    "--data-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Racine `data/` (défaut : PROJECT_ROOT/data).",
)
@click.option("--dry-run", is_flag=True, help="Compte sans rien effacer.")
def forget_cmd(
    email: str | None,
    siren: str | None,
    place_id: str | None,
    motif: str,
    data_dir: Path | None,
    dry_run: bool,
) -> None:
    """Droit à l'effacement RGPD — purge un lead de toutes les sessions."""
    if not any([email, siren, place_id]):
        console.print("[red]✗ Au moins un critère requis : --email, --siren, --place-id[/red]")
        sys.exit(2)

    data_dir = data_dir or (PROJECT_ROOT / "data")
    rapport = rgpd_forget(
        data_dir,
        email=email,
        siren=siren,
        place_id=place_id,
        motif=motif,
        dry_run=dry_run,
    )

    badge = "[yellow]DRY-RUN[/yellow]" if dry_run else "[green]EFFACÉ[/green]"
    console.print(
        f"\n{badge} — {rapport.total_lignes} lignes / "
        f"{rapport.sessions_touchees} sessions touchées\n"
    )

    table = Table(title="Détail par session")
    table.add_column("Session")
    table.add_column("Lignes", justify="right")
    table.add_column("Cache", justify="right")
    table.add_column("CSV modifiés")
    for s in rapport.sessions:
        if s.lignes_effacees == 0:
            continue
        table.add_row(
            s.session_path.name,
            str(s.lignes_effacees),
            str(s.place_ids_effaces_cache),
            ", ".join(s.csvs_modifies),
        )
    if rapport.total_lignes > 0:
        console.print(table)
    if not dry_run and rapport.total_lignes > 0:
        console.print(f"\n[dim]→ Inscrit dans {data_dir / 'effacements_log.csv'}[/dim]")


@cli.command(name="cleanup")
@click.option(
    "--older-than-days",
    type=int,
    default=365 * 3,
    show_default=True,
    help="Seuil d'ancienneté en jours (défaut : 3 ans).",
)
@click.option(
    "--mode",
    type=click.Choice(["dry-run", "archive", "delete"]),
    default="dry-run",
    show_default=True,
    help="dry-run = liste seulement ; archive = tar.gz puis supprime ; delete = supprime.",
)
@click.option(
    "--data-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Racine `data/` (défaut : PROJECT_ROOT/data).",
)
def cleanup_cmd(older_than_days: int, mode: str, data_dir: Path | None) -> None:
    """Purge les sessions plus anciennes que N jours. Dry-run par défaut."""
    data_dir = data_dir or (PROJECT_ROOT / "data")
    rapport = rgpd_cleanup(data_dir, older_than_days=older_than_days, mode=mode)

    badge = {
        "dry-run": "[yellow]DRY-RUN[/yellow]",
        "archive": "[cyan]ARCHIVÉ[/cyan]",
        "delete": "[red]SUPPRIMÉ[/red]",
    }[mode]
    console.print(
        f"\n{badge} — seuil {older_than_days} j — "
        f"{len(rapport.candidates)} session(s) concernée(s)\n"
    )

    if not rapport.candidates:
        console.print("[green]Rien à purger.[/green]")
        return

    table = Table(title="Sessions candidates")
    table.add_column("Session")
    table.add_column("Date")
    table.add_column("Taille", justify="right")
    for c in rapport.candidates:
        table.add_row(
            c.session_path.name,
            c.date_session.strftime("%Y-%m-%d"),
            _format_octets(c.taille_octets),
        )
    console.print(table)

    if mode == "dry-run":
        console.print(
            "\n[dim]Pour appliquer : --mode archive (garde tar.gz) ou --mode delete.[/dim]"
        )
    else:
        console.print(
            f"\n{rapport.actions_effectuees} action(s) effectuée(s) — "
            f"{_format_octets(rapport.octets_liberes)} libérés."
        )


# Sous-groupe veille (immatriculations VE flotte — AAA Data)
cli.add_command(veille_group)

# Sous-groupe agent Copilote (pilotage assisté/autonome)
from .cli_agent import agent_group  # noqa: E402

cli.add_command(agent_group)

# Sous-groupe cold-mail (Phase B — staging Instantly)
from .cli_cold_mail import cold_mail_group  # noqa: E402

cli.add_command(cold_mail_group)


if __name__ == "__main__":
    cli()
