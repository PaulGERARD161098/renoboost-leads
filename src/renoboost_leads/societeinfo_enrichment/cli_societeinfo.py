"""Commande CLI `enrich-societeinfo` — enrichissement firmographique autonome.

Lit un CSV de leads (L1 ou L2), appelle Societeinfo, écrit un CSV enrichi.
Indépendant du reste du pipeline : utilisable seul sur n'importe quel CSV de
sortie RénoBoost. En l'absence de clé ou avec --dry-run, données simulées.
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from ..common.budget_guard import BudgetGuard
from ..common.logger import setup_logger
from ..common.rate_limiter import RateLimiter
from ..exporter import COLONNES_STAGE2, _ecrire_csv, lire_stage2_csv
from ..settings import get_settings
from .client import (
    SocieteinfoClient,
    SocieteinfoClientConfig,
    SocieteinfoClientDryRun,
)
from .enricher import EnricheurSocieteinfo

console = Console()


COLONNES_SOCIETEINFO_EXTRA = [
    "societeinfo_siren",
    "societeinfo_naf",
    "societeinfo_libelle_naf",
    "societeinfo_effectif",
    "societeinfo_chiffre_affaires",
    "societeinfo_dirigeant",
    "societeinfo_email",
    "societeinfo_emails",
    "societeinfo_telephone",
    "societeinfo_site_web",
    "societeinfo_linkedin",
    "enrichi_societeinfo",
    "societeinfo_erreur",
    "cout_societeinfo_eur",
]
COLONNES_SOCIETEINFO = COLONNES_STAGE2 + COLONNES_SOCIETEINFO_EXTRA


@click.command(name="enrich-societeinfo")
@click.option(
    "--from-csv",
    "from_csv",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="CSV de leads à enrichir (sortie L1, L2, L3...).",
)
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="CSV de sortie. Défaut : <input>_societeinfo.csv à côté de l'entrée.",
)
@click.option(
    "--all",
    "enrichir_tout",
    is_flag=True,
    help="Enrichit TOUS les leads (sinon : seulement SIREN absent/incertain).",
)
@click.option("--budget", "budget_eur", default=10.0, show_default=True, type=float,
              help="Plafond budget € pour les appels Societeinfo.")
@click.option("--dry-run", is_flag=True,
              help="Données simulées, aucun appel réseau (test du flux).")
def enrich_societeinfo(
    from_csv: Path,
    out_path: Path | None,
    enrichir_tout: bool,
    budget_eur: float,
    dry_run: bool,
) -> None:
    """Enrichit un CSV de leads via Societeinfo (firmographie + contacts)."""
    settings = get_settings()
    out_path = out_path or from_csv.with_name(f"{from_csv.stem}_societeinfo.csv")
    setup_logger(output_dir=out_path.parent, level=settings.log_level)

    use_dry = dry_run or not settings.has_societeinfo()
    if use_dry and not dry_run:
        console.print(
            "[yellow]⚠ SOCIETEINFO_API_KEY absente → mode dry-run (données simulées).[/yellow]"
        )

    if use_dry:
        client: SocieteinfoClient = SocieteinfoClientDryRun()
    else:
        client = SocieteinfoClient(
            SocieteinfoClientConfig(
                api_key=settings.societeinfo_api_key.get_secret_value(),
                rate_limiter=RateLimiter(settings.max_requests_per_minute),
                budget=BudgetGuard(plafond_eur=budget_eur),
            )
        )

    leads = lire_stage2_csv(from_csv)
    console.print(f"[cyan]Societeinfo — {len(leads)} leads lus depuis {from_csv.name}[/cyan]")

    enricheur = EnricheurSocieteinfo(client=client, only_incertain=not enrichir_tout)
    enrichis = enricheur.enrichir(leads)

    rows = [lead.model_dump() for lead in enrichis]
    _ecrire_csv(rows, COLONNES_SOCIETEINFO, out_path)

    console.print(
        f"\n[green]✓ Enrichissement Societeinfo terminé[/green]\n"
        f"  Leads enrichis (appelés) : {enricheur.nb_enrichis}\n"
        f"  Leads trouvés            : {enricheur.nb_trouves}\n"
        f"  Coût total               : {enricheur.cout_total_eur:.2f} €\n"
        f"  CSV de sortie            : {out_path}"
    )
