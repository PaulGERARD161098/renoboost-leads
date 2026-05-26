"""Sous-groupe CLI `verticales` — lister et inspecter les verticales."""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.table import Table

from .verticale import VerticaleHorsV0Error, list_verticales, load_verticale

console = Console()


@click.group(name="verticales")
def verticales_group() -> None:
    """Verticales (offres pivotables) — list, show."""


@verticales_group.command(name="list")
def list_cmd() -> None:
    """Liste les verticales disponibles dans verticales/."""
    slugs = list_verticales()
    if not slugs:
        console.print("[yellow]Aucune verticale trouvée dans verticales/[/yellow]")
        return

    table = Table(title="Verticales disponibles")
    table.add_column("Slug", style="bold")
    table.add_column("Nom")
    table.add_column("Cible", justify="center")
    table.add_column("Secteurs", justify="right")
    table.add_column("Signaux", justify="right")

    for slug in slugs:
        try:
            v = load_verticale(slug)
            table.add_row(
                v.slug,
                v.verticale.nom,
                v.cible.type,
                str(len(v.cibles.secteurs_places)),
                str(len(v.signaux)),
            )
        except VerticaleHorsV0Error:
            table.add_row(slug, "[dim](hors V0 — B2C)[/dim]", "b2c", "—", "—")
        except Exception as e:  # noqa: BLE001
            table.add_row(slug, f"[red]invalide : {str(e)[:40]}[/red]", "—", "—", "—")

    console.print(table)


@verticales_group.command(name="show")
@click.argument("slug")
def show_cmd(slug: str) -> None:
    """Affiche le détail d'une verticale."""
    try:
        v = load_verticale(slug)
    except FileNotFoundError:
        console.print(f"[red]✗ Verticale introuvable : {slug}[/red]")
        sys.exit(1)
    except VerticaleHorsV0Error as e:
        console.print(f"[yellow]⚠ {e}[/yellow]")
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]✗ Verticale invalide : {e}[/red]")
        sys.exit(1)

    console.print(f"[bold cyan]{v.verticale.nom}[/bold cyan]  ([dim]{v.slug}[/dim])")
    console.print(f"  Cible        : {v.cible.type} — {v.cible.detail}")
    console.print(f"  Offre        : {v.offre.produit}")
    console.print(f"  Argument     : {v.offre.argument_principal}")
    console.print(f"  Ticket moyen : {v.offre.ticket_moyen_eur} €")
    console.print(
        f"  Secteurs     : {', '.join(s.query for s in v.cibles.secteurs_places)}"
    )
    console.print(f"  Signaux ({len(v.signaux)}) :")
    for s in v.signaux:
        console.print(f"    • {s}")
    console.print(f"  Seuil top    : {v.qualification.seuil_score_top}")
