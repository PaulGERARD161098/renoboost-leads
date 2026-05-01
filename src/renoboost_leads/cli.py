"""CLI principale — point d'entrée `python -m renoboost_leads.cli ...`."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import click
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from .common.budget_guard import BudgetExceededError, BudgetGuard
from .common.cache import SessionCache
from .common.logger import setup_logger
from .common.rate_limiter import RateLimiter
from .config_loader import load_campaign_config
from .exporter import (
    export_run_stats,
    export_stage1_csv,
    generer_registre_rgpd,
)
from .models import CampaignConfig, RunStats, StageStats
from .settings import PROJECT_ROOT, get_settings
from .stage1_decouverte.extractor import ExtracteurStage1
from .stage1_decouverte.geo_grid import grille_pour_zone
from .stage1_decouverte.places_client import (
    COUT_NEARBY_SEARCH_EUR,
    COUT_TEXT_SEARCH_EUR,
    PlacesClient,
    PlacesClientConfig,
)

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


# ════════════════════════════════════════════════════════════════
# Commandes
# ════════════════════════════════════════════════════════════════


@click.group()
def cli() -> None:
    """RénoBoost Leads — outil de prospection B2B paramétrable."""


# ─── check-connections ───
@cli.command(name="check-connections")
def check_connections() -> None:
    """Teste les connexions aux APIs (utilise toutes les clés présentes dans .env)."""
    settings = get_settings()

    table = Table(title="État des connexions APIs")
    table.add_column("API", style="bold")
    table.add_column("Configuré", justify="center")
    table.add_column("Test", justify="center")
    table.add_column("Détail")

    # Google Places
    if settings.has_google_places():
        # Test léger
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
            table.add_row("Google Places (New)", "✓", statut, msg[:60])
        except Exception as e:  # noqa: BLE001
            table.add_row("Google Places (New)", "✓", "[red]✗[/red]", str(e)[:60])
    else:
        table.add_row("Google Places (New)", "[red]✗[/red]", "—", "Clé absente dans .env")

    # Pappers (futur — étage 2)
    table.add_row(
        "Pappers (étage 2)",
        "[green]✓[/green]" if settings.has_pappers() else "[yellow]—[/yellow]",
        "[dim]non implémenté en L1[/dim]",
        "" if settings.has_pappers() else "Clé absente (sera utilisée en L2)",
    )

    # Dropcontact
    table.add_row(
        "Dropcontact (étage 3)",
        "[green]✓[/green]" if settings.has_dropcontact() else "[yellow]—[/yellow]",
        "[dim]non implémenté en L1[/dim]",
        "" if settings.has_dropcontact() else "Clé absente (sera utilisée en L3)",
    )

    # Anthropic
    table.add_row(
        "Anthropic Claude (étage 4)",
        "[green]✓[/green]" if settings.has_anthropic() else "[yellow]—[/yellow]",
        "[dim]non implémenté en L1[/dim]",
        "" if settings.has_anthropic() else "Clé absente (sera utilisée en L4)",
    )

    console.print(table)


# ─── estimate ───
@cli.command()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Chemin du fichier YAML de config.",
)
def estimate(config_path: Path) -> None:
    """Estime le coût et le volume d'un run AVANT lancement (zéro appel API)."""
    cfg = _load_config_or_exit(config_path)

    points = grille_pour_zone(cfg.zone)
    nb_secteurs = len(cfg.secteurs)
    nb_recherches_max = len(points) * nb_secteurs
    cout_etage1_max = nb_recherches_max * COUT_TEXT_SEARCH_EUR

    # En pratique on s'arrête au volume cible → estimation plus réaliste
    # (1 recherche renvoie ~10-15 résultats utiles en moyenne en France)
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
    table.add_row(
        "Recherches Places (max théorique)", f"{nb_recherches_max}"
    )
    table.add_row(
        "Coût étage 1 max théorique",
        f"{cout_etage1_max:.2f} €",
    )
    table.add_row(
        "[bold]Coût étage 1 estimé réaliste[/bold]",
        f"[bold]{cout_etage1_realiste:.2f} €[/bold]",
    )

    if cfg.stages.enable_stage_2_entreprises:
        cout_e2 = cfg.volume.cible * 0.12
        table.add_row("Coût étage 2 (Pappers)", f"~{cout_e2:.2f} €")
    if cfg.stages.enable_stage_3_contacts:
        cout_e3 = cfg.volume.cible * 0.20
        table.add_row("Coût étage 3 (Dropcontact)", f"~{cout_e3:.2f} €")
    if cfg.stages.enable_stage_4_prospection:
        cout_e4 = cfg.volume.cible * 0.02
        table.add_row("Coût étage 4 (Claude)", f"~{cout_e4:.2f} €")

    console.print(table)

    if cout_etage1_realiste > cfg.budget.max_eur:
        console.print(
            f"[yellow]⚠  Estimation ({cout_etage1_realiste:.2f} €) > plafond config "
            f"({cfg.budget.max_eur:.2f} €). Augmente budget.max_eur ou réduis volume.cible.[/yellow]"
        )


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
    help="Étages à exécuter, séparés par virgule. Ex: '1' ou '1,2,3,4'. "
    "L1 ne supporte que '1'.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Simulation : ne fait aucun appel API payant, retourne des leads factices.",
)
def run(config_path: Path, stages: str, dry_run: bool) -> None:
    """Lance un run de prospection."""
    cfg = _load_config_or_exit(config_path)

    # Parse les étages demandés
    try:
        stages_demandes = {int(s.strip()) for s in stages.split(",") if s.strip()}
    except ValueError:
        console.print(f"[red]✗ Format --stages invalide : '{stages}'. Ex: '1' ou '1,2'.[/red]")
        sys.exit(2)

    if stages_demandes - {1}:
        console.print(
            "[yellow]⚠  Pour cette livraison L1, seul l'étage 1 est implémenté. "
            "Les étages 2-4 seront ajoutés en L2-L4.[/yellow]"
        )

    # Préparation du dossier de sortie
    session_id = _build_session_id(cfg.run.client_name)
    output_dir = PROJECT_ROOT / "data" / "output" / session_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Logger
    logger = setup_logger(output_dir=output_dir, level=get_settings().log_level)
    logger.info("─" * 60)
    logger.info("Run %s (config: %s)", session_id, config_path)
    logger.info("Stages demandés : %s", sorted(stages_demandes))

    # Stats du run
    stats = RunStats(
        session_id=session_id,
        campaign=cfg.run.client_name,
        debut=datetime.now(timezone.utc),
    )

    # ─── Étage 1 ───
    if 1 in stages_demandes and cfg.stages.enable_stage_1_decouverte:
        if dry_run:
            logger.info("[DRY-RUN] Étage 1 simulé (aucun appel API)")
            from .models import LeadStage1
            leads = [
                LeadStage1(
                    place_id=f"FAKE_{i}",
                    extraction_date=datetime.now(timezone.utc),
                    nom=f"Établissement test {i}",
                    adresse=f"{i} rue Fictive, 34000 Montpellier",
                    ville="Montpellier",
                    code_postal="34000",
                    note=4.2,
                    nb_avis=42,
                )
                for i in range(min(10, cfg.volume.cible))
            ]
        else:
            api_key = _check_google_key_or_exit()
            t0 = datetime.now(timezone.utc)

            settings = get_settings()
            limiter = RateLimiter(settings.max_requests_per_minute)
            budget = BudgetGuard(plafond_eur=cfg.budget.max_eur)
            client = PlacesClient(
                PlacesClientConfig(
                    api_key=api_key,
                    rate_limiter=limiter,
                    budget=budget,
                )
            )
            cache = SessionCache(output_dir / "cache.sqlite")
            extracteur = ExtracteurStage1(client=client, config=cfg, cache=cache)

            try:
                leads = extracteur.extraire()
            except BudgetExceededError as e:
                logger.error("Budget dépassé en cours de run : %s", e)
                console.print(f"[red]✗ Budget dépassé : {e}[/red]")
                console.print("[yellow]Les leads collectés avant l'arrêt sont sauvegardés.[/yellow]")
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

        # Export CSV
        csv_path = output_dir / "etage1_decouverte.csv"
        export_stage1_csv(leads, csv_path)
        stats.leads_finaux = len(leads)

        # Registre RGPD
        generer_registre_rgpd(
            output_path=output_dir / "registre_rgpd.md",
            client_name=cfg.run.client_name,
            nb_leads=len(leads),
            sources=["Google Places API (New) — données publiques"],
        )

        console.print(
            f"\n[green]✓ Étage 1 terminé : {len(leads)} leads → {csv_path}[/green]"
        )
        if not dry_run:
            console.print(
                f"   Coût estimé : [bold]{stats.etages_executes[-1].cout_eur_estime:.4f} €[/bold]"
            )

    # Finalisation
    stats.fin = datetime.now(timezone.utc)
    stats.duree_totale_secondes = (stats.fin - stats.debut).total_seconds()
    export_run_stats(stats, output_dir / "stats_run.json")

    console.print(f"\n[bold]Sortie complète :[/bold] {output_dir}")


if __name__ == "__main__":
    cli()
