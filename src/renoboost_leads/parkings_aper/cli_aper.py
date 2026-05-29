"""Sous-commandes CLI `aper` (à monter sur le groupe `cli` principal)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click
from rich.console import Console

from ..common.logger import setup_logger
from ..config_loader import load_campaign_config
from ..models import ClaudeScoring, FiltresEntreprise
from ..settings import PROJECT_ROOT, get_settings
from .models import AperConfig
from .pipeline_aper import AperRunConfig, executer_cycle_aper

console = Console()


@click.group(name="aper")
def aper_group() -> None:
    """Parkings loi APER — prospects ombrières PV contraints (> 1 500 m²)."""


@aper_group.command(name="run")
@click.option(
    "--fichier",
    "fichier_parkings",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="CSV inventaire parkings (export OSM/IGN ou fichier client).",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="YAML campagne (filtres_entreprise + claude_scoring). Si omis : défauts.",
)
@click.option("--source", default="aper_osm", show_default=True,
              help="Identifiant de la source (traçabilité CSV).")
@click.option("--surface-min", "surface_min", type=float, default=None,
              help="Seuil de surface m² (défaut 1500 = seuil légal APER).")
@click.option("--budget", "budget_eur", default=5.0, show_default=True, type=float,
              help="Plafond budget € pour le scoring L4 (Claude).")
@click.option("--dry-run", is_flag=True,
              help="Simulation L4 (scores factices, pas d'appel Anthropic).")
def aper_run(
    fichier_parkings: Path,
    config_path: Path | None,
    source: str,
    surface_min: float | None,
    budget_eur: float,
    dry_run: bool,
) -> None:
    """Lance un run parkings APER sur un CSV inventaire."""
    settings = get_settings()

    filtres_entreprise = FiltresEntreprise()
    claude_scoring = ClaudeScoring()
    client_name = "aper"
    if config_path is not None:
        try:
            cfg = load_campaign_config(config_path)
            filtres_entreprise = cfg.filtres_entreprise
            claude_scoring = cfg.claude_scoring
            client_name = cfg.run.client_name
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]✗ Config YAML invalide : {e}[/red]")
            raise SystemExit(2) from e

    if not dry_run and not settings.has_anthropic():
        console.print(
            "[red]✗ ANTHROPIC_API_KEY manquante.[/red] "
            "Ajoute-la dans .env ou lance avec --dry-run."
        )
        raise SystemExit(2)

    aper_config = AperConfig()
    if surface_min is not None:
        aper_config = aper_config.model_copy(update={"surface_min_m2": surface_min})

    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
    output_dir = PROJECT_ROOT / "data" / "parkings_aper" / f"{date_str}_{client_name}_{source}"
    output_dir.mkdir(parents=True, exist_ok=True)
    setup_logger(output_dir=output_dir, level=settings.log_level)

    run_config = AperRunConfig(
        source_aper=source,
        aper_config=aper_config,
        filtres_entreprise=filtres_entreprise,
        claude_scoring=claude_scoring,
        budget_eur=budget_eur,
        anthropic_api_key=(
            settings.anthropic_api_key.get_secret_value() if settings.has_anthropic() else None
        ),
        dry_run_l4=dry_run,
    )

    console.print(
        f"[cyan]Parkings APER {source} — fichier : {fichier_parkings.name}[/cyan]\n"
        f"[cyan]Seuil : {aper_config.surface_min_m2:.0f} m² — Sortie : {output_dir}[/cyan]"
    )

    resultat = executer_cycle_aper(
        fichier_parkings=fichier_parkings,
        output_dir=output_dir,
        config=run_config,
    )
    csv_final = output_dir / "parkings_aper_leads.csv"

    console.print(
        f"\n[green]✓ Run APER terminé[/green]\n"
        f"  Lignes brutes            : {resultat.nb_lignes_brutes}\n"
        f"  Parkings soumis APER      : {resultat.nb_parkings_aper}\n"
        f"    ↳ nouveaux              : {resultat.nb_nouveaux}\n"
        f"    ↳ déjà vus (flagués)    : {resultat.nb_deja_vus}\n"
        f"  Top leads (score ≥ {claude_scoring.seuil_top_lead}) : {resultat.nb_top_leads}\n"
        f"  Coût L4                   : {resultat.cout_l4_eur:.4f} €\n"
        f"  CSV final                 : {csv_final}"
    )
