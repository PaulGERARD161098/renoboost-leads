"""Sous-commandes CLI `veille` (à monter sur le groupe `cli` principal)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click
from rich.console import Console

from ..common.logger import setup_logger
from ..config_loader import load_campaign_config
from ..models import ClaudeScoring, FiltresEntreprise
from ..settings import PROJECT_ROOT, get_settings
from .mailer import ConfigSMTP
from .models import VeilleConfig
from .pipeline_veille import VeilleRunConfig, executer_cycle_veille

console = Console()


@click.group(name="veille")
def veille_group() -> None:
    """Veille immatriculations — sources externes (AAA Data, etc.)."""


@veille_group.command(name="run")
@click.option(
    "--fichier",
    "fichier_aaa",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Fichier CSV AAA Data du jour à ingérer.",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=False,
    default=None,
    help="YAML campagne (pour récupérer filtres_entreprise + claude_scoring). "
    "Si omis : défauts Pydantic.",
)
@click.option(
    "--source",
    default="aaa_data",
    show_default=True,
    help="Identifiant de la source (pour traçabilité dans le CSV).",
)
@click.option(
    "--budget",
    "budget_eur",
    default=5.0,
    show_default=True,
    type=float,
    help="Plafond budget € pour l'étape L4 (scoring Claude).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Simulation L4 (ClaudeClientDryRun) — pas d'appel Anthropic, scores factices.",
)
@click.option(
    "--no-email",
    is_flag=True,
    help="Désactive l'envoi email post-run même si SMTP est configuré dans .env.",
)
def veille_run(
    fichier_aaa: Path,
    config_path: Path | None,
    source: str,
    budget_eur: float,
    dry_run: bool,
    no_email: bool,
) -> None:
    """Lance un cycle de veille sur un CSV AAA Data."""
    settings = get_settings()

    # Charger la config YAML si fournie (récupère filtres + claude_scoring + nom client)
    filtres_entreprise = FiltresEntreprise()
    claude_scoring = ClaudeScoring()
    client_name = "veille"
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

    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
    output_dir = PROJECT_ROOT / "data" / "veille" / f"{date_str}_{client_name}_{source}"
    output_dir.mkdir(parents=True, exist_ok=True)

    setup_logger(output_dir=output_dir, level=settings.log_level)

    smtp_config: ConfigSMTP | None = None
    if settings.has_smtp() and not no_email:
        smtp_config = ConfigSMTP(
            host=settings.smtp_host,
            port=settings.smtp_port,
            user=settings.smtp_user,
            password=settings.smtp_password.get_secret_value(),
            expediteur=settings.smtp_from,
            destinataires=settings.smtp_destinataires_list(),
            use_tls=settings.smtp_use_tls,
        )

    run_config = VeilleRunConfig(
        source_veille=source,
        veille_config=VeilleConfig(),
        filtres_entreprise=filtres_entreprise,
        claude_scoring=claude_scoring,
        budget_eur=budget_eur,
        anthropic_api_key=(
            settings.anthropic_api_key.get_secret_value() if settings.has_anthropic() else None
        ),
        dry_run_l4=dry_run,
        smtp_config=smtp_config,
    )

    console.print(
        f"[cyan]Veille {source} — fichier : {fichier_aaa.name}[/cyan]\n"
        f"[cyan]Sortie : {output_dir}[/cyan]"
    )

    resultat = executer_cycle_veille(
        fichier_aaa=fichier_aaa,
        output_dir=output_dir,
        config=run_config,
    )
    csv_final = output_dir / "veille_leads.csv"  # déjà écrit par le pipeline

    console.print(
        f"\n[green]✓ Veille terminée[/green]\n"
        f"  Lignes AAA brutes      : {resultat.nb_lignes_brutes}\n"
        f"  VE flotte entreprise    : {resultat.nb_ve_flotte}\n"
        f"    ↳ nouveaux SIREN      : {resultat.nb_nouveaux}\n"
        f"    ↳ déjà vus (flagués)  : {resultat.nb_deja_vus}\n"
        f"  Top leads (score ≥ {claude_scoring.seuil_top_lead}) : {resultat.nb_top_leads}\n"
        f"  Coût L4                 : {resultat.cout_l4_eur:.4f} €\n"
        f"  CSV final               : {csv_final}"
    )
