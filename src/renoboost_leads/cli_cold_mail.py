"""CLI cold mail — validation manuelle des stagings + envoi.

Commandes :
- `cold-mail stage --session-id X --from-email Y` : crée un staging depuis le L4
- `cold-mail list` : tableau des stagings (id, secteur, total, par état)
- `cold-mail show <staging_id>` : preview détaillée d'un staging (chaque email)
- `cold-mail validate --staging-id X --lead-id Y` : marque 'valide'
- `cold-mail refuse --staging-id X --lead-id Y` : marque 'refuse'
- `cold-mail send --staging-id X` : pousse les 'valide' vers Instantly
- `cold-mail metrics --campaign-id Z` : lit les métriques d'une campagne
"""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@click.group(name="cold-mail")
def cold_mail_group() -> None:
    """Cold mailing — validation manuelle + envoi Instantly."""


@cold_mail_group.command(name="list")
def cold_mail_list() -> None:
    """Liste les stagings en cours (avec compteurs par état)."""
    from .instantly.staging import StagingStore

    items = StagingStore().list()
    if not items:
        console.print("[dim]Aucun staging.[/dim]")
        return
    t = Table(title="Stagings cold mail")
    t.add_column("Staging ID")
    t.add_column("Secteur")
    t.add_column("Session")
    t.add_column("Total", justify="right")
    t.add_column("En attente", justify="right")
    t.add_column("Validé", justify="right")
    t.add_column("Refusé", justify="right")
    t.add_column("Envoyé", justify="right")
    for s in items:
        e = s["etats"]
        t.add_row(
            s["staging_id"],
            s.get("secteur") or "?",
            s.get("session_id") or "?",
            str(s["total"]),
            str(e.get("en_attente", 0)),
            str(e.get("valide", 0)),
            str(e.get("refuse", 0)),
            str(e.get("envoye", 0)),
        )
    console.print(t)


@cold_mail_group.command(name="show")
@click.argument("staging_id")
def cold_mail_show(staging_id: str) -> None:
    """Affiche tous les emails d'un staging avec leur état."""
    from .instantly.staging import StagingStore

    try:
        s = StagingStore().load(staging_id)
    except FileNotFoundError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)
    console.print(
        Panel.fit(
            f"[bold]{staging_id}[/bold]\n"
            f"Secteur     : {s.secteur}\n"
            f"Session     : {s.session_id}\n"
            f"From        : {s.from_email}\n"
            f"Créé le     : {s.cree_le}\n"
            f"Items       : {len(s.items)}",
            border_style="cyan",
        )
    )
    for item in s.items:
        couleur = {
            "en_attente": "yellow",
            "valide": "green",
            "refuse": "red",
            "envoye": "blue",
        }.get(item.etat, "white")
        console.print(
            Panel(
                f"[bold]Sujet[/bold] : {item.sujet}\n\n{item.corps}",
                title=(
                    f"[{couleur}]{item.lead_id}[/{couleur}]  "
                    f"→ {item.email_dest}  ({item.nom_dest})  "
                    f"[{couleur}][{item.etat}][/{couleur}]"
                ),
                border_style=couleur,
            )
        )


@cold_mail_group.command(name="stage")
@click.option("--session-id", required=True, help="Session du pipeline (dossier data/output/).")
@click.option("--from-email", required=True, help="Email expéditeur de la campagne.")
@click.option("--secteur", default="pipeline", show_default=True)
@click.option(
    "--min-score",
    type=int,
    default=None,
    help="Élargit la sélection aux leads score_interet >= min-score (sinon top_lead).",
)
def cold_mail_stage(
    session_id: str, from_email: str, secteur: str, min_score: int | None
) -> None:
    """Crée un staging cold-mail depuis le L4 d'une session (aucun envoi)."""
    from .instantly.stager import stager_session

    try:
        res = stager_session(
            session_id,
            from_email=from_email,
            secteur=secteur,
            min_score=min_score,
        )
    except FileNotFoundError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)
    console.print(
        f"[green]✓ Staging créé : {res.staging_id}[/green] — "
        f"{res.nb_stages} email(s) en attente · "
        f"{res.nb_sans_email} sans email · {res.nb_sous_seuil} hors sélection.\n"
        f"Relire : [bold]cold-mail show {res.staging_id}[/bold]"
    )


@cold_mail_group.command(name="validate")
@click.option("--staging-id", required=True)
@click.option("--lead-id", required=True)
def cold_mail_validate(staging_id: str, lead_id: str) -> None:
    """Marque un item comme 'valide' (prêt à envoyer)."""
    _set_etat(staging_id, lead_id, "valide")


@cold_mail_group.command(name="refuse")
@click.option("--staging-id", required=True)
@click.option("--lead-id", required=True)
def cold_mail_refuse(staging_id: str, lead_id: str) -> None:
    """Marque un item comme 'refuse' (ne sera jamais envoyé)."""
    _set_etat(staging_id, lead_id, "refuse")


def _set_etat(staging_id: str, lead_id: str, etat: str) -> None:
    from .instantly.staging import StagingStore

    try:
        s = StagingStore().set_etat(staging_id, lead_id, etat)
    except (FileNotFoundError, KeyError, ValueError) as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)
    item = next(i for i in s.items if i.lead_id == lead_id)
    console.print(
        f"[green]✓[/green] {staging_id}/{lead_id} → "
        f"état [bold]{item.etat}[/bold] ({item.email_dest})"
    )


@cold_mail_group.command(name="send")
@click.option("--staging-id", required=True)
def cold_mail_send(staging_id: str) -> None:
    """Pousse les items 'valide' du staging vers Instantly."""
    from .agent.tools.cold_mail import send_validated

    res = send_validated(staging_id)
    if "error" in res:
        console.print(f"[red]✗ {res['error']}[/red]")
        sys.exit(1)
    if "warning" in res:
        console.print(f"[yellow]⚠ {res['warning']}[/yellow]")
        return
    mode = "[yellow]DRY-RUN[/yellow]" if res.get("dry_run") else "[green]LIVE[/green]"
    console.print(
        Panel.fit(
            f"[bold]Envoi terminé[/bold] {mode}\n"
            f"Staging      : {res['staging_id']}\n"
            f"Campaign     : {res['campaign_id']}\n"
            f"Envoyés      : {res['envoyes']}\n"
            f"Compteurs    : {res.get('compteurs')}",
            border_style="green" if not res.get("dry_run") else "yellow",
        )
    )


@cold_mail_group.command(name="metrics")
@click.option("--campaign-id", required=True)
def cold_mail_metrics(campaign_id: str) -> None:
    """Affiche les métriques d'une campagne Instantly."""
    from .agent.tools.cold_mail import read_campaign_metrics

    res = read_campaign_metrics(campaign_id)
    if "error" in res:
        console.print(f"[red]✗ {res['error']}[/red]")
        sys.exit(1)
    console.print(
        Panel.fit(
            f"[bold]Métriques campagne[/bold]\n"
            f"Campaign     : {campaign_id}\n"
            f"Sent         : {res.get('sent', 0)}\n"
            f"Opened       : {res.get('opened', 0)}\n"
            f"Clicked      : {res.get('clicked', 0)}\n"
            f"Replied      : {res.get('replied', 0)}\n"
            f"Bounced      : {res.get('bounced', 0)}"
            + ("  [yellow](dry-run)[/yellow]" if res.get("dry_run") else ""),
            border_style="cyan",
        )
    )
