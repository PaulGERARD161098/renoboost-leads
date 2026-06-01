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
from .common.budget_guard import BudgetGuard
from .common.logger import setup_logger
from .common.rate_limiter import RateLimiter
from .config_loader import load_campaign_config
from .exporter import (
    export_csv_crm,
    export_run_stats,
    generer_registre_rgpd,
    lire_stage3_5_csv,
    lire_stage3_csv,
    lire_stage4_csv,
)
from .models import CampaignConfig, RunStats
from .orchestrateur import executer_pipeline
from .settings import PROJECT_ROOT, get_settings
from .stage1_decouverte.geo_grid import grille_pour_zone
from .stage1_decouverte.places_client import (
    COUT_TEXT_SEARCH_EUR,
    PlacesClient,
    PlacesClientConfig,
)
from .stage2_entreprises.recherche_client import (
    RechercheClientConfig,
    RechercheEntreprisesClient,
)
from .veille_immatriculations.cli_veille import veille_group
from .verticale import VerticaleHorsV0Error, load_verticale

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


def _appliquer_verticale(cfg: CampaignConfig, slug: str) -> None:
    """Surcharge le ciblage de `cfg` à partir de la verticale `slug`.

    La verticale est la source de vérité du CIBLAGE : secteurs Places (L1) et
    filtres entreprise NAF (L2) viennent du même fichier, ce qui garantit leur
    cohérence (évite le décalage L1↔NAF). La config conserve les paramètres
    opérationnels (zone, volume, budget, émetteur). Seul le B2B est exploitable
    en V0 ; toute erreur de chargement termine le run avec le code 2.
    """
    try:
        verticale = load_verticale(slug)
    except FileNotFoundError:
        console.print(f"[red]✗ Verticale introuvable : '{slug}'.[/red]")
        sys.exit(2)
    except VerticaleHorsV0Error as exc:
        console.print(f"[red]✗ {exc}[/red]")
        sys.exit(2)
    except (ValueError, ValidationError) as exc:
        console.print(f"[red]✗ Verticale '{slug}' invalide : {exc}[/red]")
        sys.exit(2)

    cfg.secteurs = verticale.cibles.secteurs_places
    cfg.filtres_entreprise = verticale.cibles.filtres_entreprise
    console.print(
        f"[cyan]Verticale '{verticale.slug}' : {len(cfg.secteurs)} secteur(s) L1 "
        f"+ filtres NAF L2 appliqués (ciblage aligné).[/cyan]"
    )


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
@click.option(
    "--l2-provider",
    "l2_provider",
    type=click.Choice(["datagouv", "societeinfo"]),
    default="datagouv",
    show_default=True,
    help="Provider étage 2 : data.gouv (gratuit) ou societeinfo (payant, registres officiels).",
)
@click.option(
    "--verticale",
    "verticale_slug",
    default=None,
    help="Slug d'une verticale (verticales/<slug>/verticale.yaml) : surcharge le "
    "ciblage L1 (secteurs Places) et les filtres NAF L2 pour garantir leur cohérence.",
)
def run(
    config_path: Path,
    stages: str,
    from_csv_path: Path | None,
    dry_run: bool,
    l2_provider: str,
    verticale_slug: str | None,
) -> None:
    """Lance un run de prospection."""
    cfg = _load_config_or_exit(config_path)
    if verticale_slug:
        _appliquer_verticale(cfg, verticale_slug)

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

    if any(s not in (0, 1, 2, 3, 3.5, 3.7, 4) for s in stages_demandes):
        console.print(
            "[yellow]⚠  Étages valides : 0, 1, 2, 3, 3.5, 3.7, 4. "
            "Étages inconnus ignorés.[/yellow]"
        )
        stages_demandes = [s for s in stages_demandes if s in (0, 1, 2, 3, 3.5, 3.7, 4)]

    if not stages_demandes:
        console.print("[red]✗ Aucun étage valide demandé.[/red]")
        sys.exit(2)

    # ─── Résolution du dossier de sortie ───
    if from_csv_path:
        # On reprend dans le dossier du CSV existant
        output_dir = from_csv_path.parent
        session_id = output_dir.name
        console.print(f"[cyan]Mode reprise depuis : {from_csv_path}[/cyan]")
    elif 1 not in stages_demandes and 0 not in stages_demandes:
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
        emetteur_email=cfg.emetteur.email if cfg.emetteur else None,
    )

    settings = get_settings()

    result = executer_pipeline(
        cfg,
        settings,
        stages_demandes,
        output_dir,
        stats,
        from_csv_path=from_csv_path,
        l2_provider=l2_provider,
        dry_run=dry_run,
        logger=logger,
    )
    sources_rgpd = result.sources_rgpd
    nb_leads_finaux = result.nb_leads_finaux
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

# Sous-groupe parkings APER (prospects ombrières contraints loi APER)
from .parkings_aper.cli_aper import aper_group  # noqa: E402

cli.add_command(aper_group)

# Commande enrich-societeinfo (enrichissement firmographique autonome)
from .societeinfo_enrichment.cli_societeinfo import enrich_societeinfo  # noqa: E402

cli.add_command(enrich_societeinfo)


if __name__ == "__main__":
    cli()
