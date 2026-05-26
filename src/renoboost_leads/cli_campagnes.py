"""Sous-groupe CLI `campagnes` — lister et inspecter les campagnes."""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.table import Table

from .campagne import (
    composer_campaign_config,
    list_campagnes,
    load_campagne,
    persister_config_lancable,
)
from .verticale import VerticaleHorsV0Error, load_verticale

console = Console()


@click.group(name="campagnes")
def campagnes_group() -> None:
    """Campagnes (verticale + zone + volume + budget) — list, show."""


@campagnes_group.command(name="list")
def list_cmd() -> None:
    """Liste les campagnes disponibles dans campagnes/."""
    ids = list_campagnes()
    if not ids:
        console.print("[yellow]Aucune campagne trouvée dans campagnes/[/yellow]")
        return

    table = Table(title="Campagnes disponibles")
    table.add_column("Id", style="bold")
    table.add_column("Verticale")
    table.add_column("Zone")
    table.add_column("Volume", justify="right")
    table.add_column("Budget €", justify="right")

    for cid in ids:
        try:
            c = load_campagne(cid)
            table.add_row(
                c.id,
                c.verticale_slug,
                f"{c.zone.type}:{','.join(c.zone.codes)}",
                str(c.volume.cible),
                f"{c.budget.max_eur:g}",
            )
        except Exception as e:  # noqa: BLE001
            table.add_row(cid, f"[red]invalide : {str(e)[:40]}[/red]", "—", "—", "—")

    console.print(table)


@campagnes_group.command(name="show")
@click.argument("campagne_id")
def show_cmd(campagne_id: str) -> None:
    """Affiche une campagne + l'aperçu de la config composée (lançable)."""
    try:
        c = load_campagne(campagne_id)
    except FileNotFoundError:
        console.print(f"[red]✗ Campagne introuvable : {campagne_id}[/red]")
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]✗ Campagne invalide : {e}[/red]")
        sys.exit(1)

    console.print(
        f"[bold cyan]{c.campagne.nom or c.id}[/bold cyan]  ([dim]{c.id}[/dim])"
    )
    console.print(f"  Verticale : {c.verticale_slug}")
    console.print(f"  Zone      : {c.zone.type} — {', '.join(c.zone.codes)}")
    console.print(f"  Volume    : {c.volume.cible} leads cible")
    console.print(f"  Budget    : {c.budget.max_eur:g} €")

    try:
        v = load_verticale(c.verticale_slug)
    except (FileNotFoundError, VerticaleHorsV0Error) as e:
        console.print(f"[yellow]⚠ Verticale non exploitable : {e}[/yellow]")
        return

    cfg = composer_campaign_config(c, v)
    console.print("\n[bold]Config composée (lançable)[/bold]")
    console.print(f"  client_name : {cfg.run.client_name}")
    console.print(f"  secteurs    : {', '.join(s.query for s in cfg.secteurs)}")
    console.print(f"  seuil top   : {cfg.claude_scoring.seuil_top_lead}")
    console.print(f"  L3.5 actif  : {cfg.stages.enable_stage_3_5_enrichment}")


@campagnes_group.command(name="run")
@click.argument("campagne_id")
@click.option(
    "--stages",
    default="1,2,3,3.5,4",
    help="Étages à exécuter, séparés par virgule (défaut : pipeline complet).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Simulation gratuite : aucun appel API payant.",
)
def run_cmd(campagne_id: str, stages: str, dry_run: bool) -> None:
    """Lance le pipeline depuis une campagne (compose la config puis run)."""
    try:
        c = load_campagne(campagne_id)
        v = load_verticale(c.verticale_slug)
    except FileNotFoundError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)
    except VerticaleHorsV0Error as e:
        console.print(f"[yellow]⚠ {e}[/yellow]")
        sys.exit(1)

    chemin = persister_config_lancable(c, v)
    console.print(f"[cyan]Config lançable écrite : {chemin}[/cyan]")
    if not dry_run:
        console.print(
            f"[yellow]⚠ Lancement réel — budget plafonné à {c.budget.max_eur:g} €.[/yellow]"
        )

    # Réutilise la commande `run` existante (pipeline complet, budget guard, snapshots).
    from .cli import run as run_pipeline

    run_pipeline.callback(
        config_path=chemin, stages=stages, from_csv_path=None, dry_run=dry_run
    )
