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
    backup_csv,
    export_run_stats,
    export_stage1_csv,
    export_stage2_csv,
    export_stage3_csv,
    export_stage3_csv_separe_hors_filtre,
    generer_registre_rgpd,
    lire_stage1_csv,
    lire_stage2_csv,
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
from .stage2_entreprises.recherche_client import (
    RechercheClientConfig,
    RechercheEntreprisesClient,
)
from .stage3_contacts.enricher import EnricheurStage3
from .stage3_contacts.scraper import ScraperContact

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

    # Anthropic (étage 4) — non implémenté en L2/L3
    table.add_row(
        "Anthropic Claude (étage 4)",
        "[green]✓[/green]" if settings.has_anthropic() else "[yellow]—[/yellow]",
        "[dim]non implémenté[/dim]",
        "" if settings.has_anthropic() else "Clé optionnelle (sera utilisée en L4)",
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
        cout_e4 = cfg.volume.cible * 0.02
        table.add_row("Coût étage 4 (Claude)", f"~{cout_e4:.2f} €")

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

    # Parse les étages demandés
    try:
        stages_demandes = sorted({int(s.strip()) for s in stages.split(",") if s.strip()})
    except ValueError:
        console.print(f"[red]✗ Format --stages invalide : '{stages}'.[/red]")
        sys.exit(2)

    if any(s not in (1, 2, 3) for s in stages_demandes):
        console.print(
            "[yellow]⚠  Seuls les étages 1, 2, 3 sont implémentés. "
            "L'étage 4 sera ajouté en livraison L4.[/yellow]"
        )
        stages_demandes = [s for s in stages_demandes if s in (1, 2, 3)]

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
            leads_l2=leads_l2,
            cache=cache,
            output_dir=output_dir,
            stats=stats,
        )
        sources_rgpd.append(
            "Mentions légales / pages contact des sites web (LCEN — données publiques)"
        )
        sources_rgpd.append("Génération de patterns d'emails (logique algorithmique)")

    # ─── Finalisation : registre RGPD + stats ───
    nb_leads_finaux = (
        len(leads_l3)
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
    export_run_stats(stats, output_dir / "stats_run.json")

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


def _executer_stage2(cfg, leads_l1, cache, output_dir, stats):
    """Exécute l'étage 2."""
    csv_path = output_dir / "etage2_entreprises.csv"
    t0 = datetime.now(timezone.utc)

    def callback_save(leads_partial):
        export_stage2_csv(leads_partial, csv_path)

    limiter = RateLimiter(60)  # 60 req/min, largement sous la limite de 7 req/s
    rech_client = RechercheEntreprisesClient(RechercheClientConfig(rate_limiter=limiter))
    enricheur = EnricheurStage2(
        client=rech_client,
        cache=cache,
        callback_save_incremental=callback_save,
        filtres_entreprise=cfg.filtres_entreprise,
    )

    leads_l2 = enricheur.enrichir(leads_l1)
    duree = (datetime.now(timezone.utc) - t0).total_seconds()

    # Sauvegarde finale
    export_stage2_csv(leads_l2, csv_path)
    backup_csv(csv_path)

    # Stats
    stats_e2 = enricheur.stats_l2(leads_l2)
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
            cout_eur_estime=0.0,
            leads_collectes=len(leads_l2),
        )
    )

    console.print(
        f"\n[green]✓ Étage 2 : {len(leads_l2)} leads enrichis → {csv_path.name}[/green]\n"
        f"   SIREN trouvé : {stats_e2.get('siren_pct', 0)}% — "
        f"Dirigeant trouvé : {stats_e2.get('dirigeant_pct', 0)}% — "
        f"Chaînes : {stats_e2.get('chaines_pct', 0)}%"
    )
    return leads_l2


def _executer_stage3(leads_l2, cache, output_dir, stats):
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
    return leads_l3


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


if __name__ == "__main__":
    cli()
