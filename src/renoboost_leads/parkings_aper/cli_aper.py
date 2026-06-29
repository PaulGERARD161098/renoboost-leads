"""Sous-commandes CLI `aper` (à monter sur le groupe `cli` principal)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click
from rich.console import Console

from ..common.logger import setup_logger
from ..config_loader import load_campaign_config
from ..models import ClaudeScoring, EnrichissementL35, FiltresEntreprise
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
              help="Seuil bas de surface m² (défaut 1500 = seuil légal APER).")
@click.option("--surface-max", "surface_max", type=float, default=None,
              help="Plafond de surface m² (défaut : aucun). Ex. 1250 ≈ 50 places "
                   "pour cibler les petits parkings 'flotte'.")
@click.option("--budget", "budget_eur", default=5.0, show_default=True, type=float,
              help="Plafond budget € pour L3.5 Dropcontact (l'étage payant ~0,10 €/lead).")
@click.option("--budget-l4", "budget_l4_eur", default=5.0, show_default=True, type=float,
              help="Plafond budget € pour le scoring L4 Claude (indépendant de L3.5, "
                   "quasi-gratuit ~0,002 €/lead — ne pas affamer).")
@click.option("--dry-run", is_flag=True,
              help="Simulation L4 (scores factices, pas d'appel Anthropic).")
@click.option("--enrichir-l35", "enrichir_l35", is_flag=True,
              help="Active L3.5 Dropcontact (email/tél/LinkedIn décideur) entre L3 et L4. "
                   "Sans clé Dropcontact : dry-run (emails simulés).")
@click.option("--vers-staging", is_flag=True,
              help="Pousse les top leads dans le staging cold-mail Instantly (validation N2).")
@click.option("--min-score", "min_score", type=int, default=None,
              help="Avec --vers-staging : élargit aux leads de score ≥ N (défaut : top leads).")
@click.option("--from-email", "from_email", default="",
              help="Avec --vers-staging : adresse expéditeur du staging.")
@click.option("--no-geo", is_flag=True,
              help="Désactive la résolution géoloc → SIREN des parkings sans enseigne (Phase C).")
@click.option("--rayon-geo", "rayon_geo_km", type=float, default=None,
              help="Rayon (km) near_point pour la résolution géoloc. Défaut : AUTO "
                   "(50 m en mode flotte si --surface-max < 1500, sinon 200 m).")
@click.option("--rate-limit", "rate_limit_per_min", type=int, default=60, show_default=True,
              help="Débit max d'appels/min vers recherche-entreprises (Phase C + L2). "
                   "Baisser (ex. 30) si l'API renvoie des HTTP 429.")
@click.option("--no-email", is_flag=True,
              help="N'envoie pas l'email récapitulatif post-run même si SMTP est configuré.")
def aper_run(
    fichier_parkings: Path,
    config_path: Path | None,
    source: str,
    surface_min: float | None,
    surface_max: float | None,
    budget_eur: float,
    budget_l4_eur: float,
    dry_run: bool,
    enrichir_l35: bool,
    vers_staging: bool,
    min_score: int | None,
    from_email: str,
    no_geo: bool,
    rayon_geo_km: float | None,
    rate_limit_per_min: int,
    no_email: bool,
) -> None:
    """Lance un run parkings APER sur un CSV inventaire."""
    settings = get_settings()

    filtres_entreprise = FiltresEntreprise()
    claude_scoring = ClaudeScoring()
    enrichissement_l3_5 = EnrichissementL35()
    client_name = "aper"
    if config_path is not None:
        try:
            cfg = load_campaign_config(config_path)
            filtres_entreprise = cfg.filtres_entreprise
            claude_scoring = cfg.claude_scoring
            enrichissement_l3_5 = cfg.enrichissement_l3_5
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
    maj_surface: dict[str, float] = {}
    if surface_min is not None:
        maj_surface["surface_min_m2"] = surface_min
    if surface_max is not None:
        maj_surface["surface_max_m2"] = surface_max
    if maj_surface:
        aper_config = aper_config.model_copy(update=maj_surface)

    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
    output_dir = PROJECT_ROOT / "data" / "parkings_aper" / f"{date_str}_{client_name}_{source}"
    output_dir.mkdir(parents=True, exist_ok=True)
    setup_logger(output_dir=output_dir, level=settings.log_level)

    smtp_config = None
    if settings.has_smtp() and not no_email:
        from ..veille_immatriculations.mailer import ConfigSMTP

        smtp_config = ConfigSMTP(
            host=settings.smtp_host,
            port=settings.smtp_port,
            user=settings.smtp_user,
            password=settings.smtp_password.get_secret_value(),
            expediteur=settings.smtp_from,
            destinataires=settings.smtp_destinataires_list(),
            use_tls=settings.smtp_use_tls,
        )

    run_config = AperRunConfig(
        source_aper=source,
        aper_config=aper_config,
        filtres_entreprise=filtres_entreprise,
        claude_scoring=claude_scoring,
        budget_eur=budget_eur,
        budget_l4_eur=budget_l4_eur,
        anthropic_api_key=(
            settings.anthropic_api_key.get_secret_value() if settings.has_anthropic() else None
        ),
        dry_run_l4=dry_run,
        enrichir_l3_5=enrichir_l35,
        enrichissement_l3_5=enrichissement_l3_5,
        dropcontact_api_key=(
            settings.dropcontact_api_key.get_secret_value()
            if settings.has_dropcontact()
            else None
        ),
        resoudre_geo=not no_geo,
        rayon_geo_km=rayon_geo_km,
        rate_limit_per_min=rate_limit_per_min,
        smtp_config=smtp_config,
    )

    if enrichir_l35 and not settings.has_dropcontact():
        console.print(
            "[yellow]⚠  --enrichir-l35 sans DROPCONTACT_API_KEY : "
            "L3.5 en dry-run (emails simulés).[/yellow]"
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
        f"    ↳ résolus par géoloc    : {resultat.nb_resolus_geo}\n"
        f"    ↳ nouveaux              : {resultat.nb_nouveaux}\n"
        f"    ↳ déjà vus (flagués)    : {resultat.nb_deja_vus}\n"
        f"  Top leads (score ≥ {claude_scoring.seuil_top_lead}) : {resultat.nb_top_leads}\n"
        + (
            f"  Emails L3.5 (Dropcontact) : {resultat.nb_emails_l35} "
            f"(coût {resultat.cout_l35_eur:.2f} €)\n"
            if enrichir_l35
            else ""
        )
        + f"  Coût L4                   : {resultat.cout_l4_eur:.4f} €\n"
        f"  CSV final                 : {csv_final}"
    )

    if resultat.raison_degradation:
        console.print(
            f"[yellow]⚠  Run dégradé : {resultat.raison_degradation}[/yellow]"
        )

    _staging_post_run(vers_staging, resultat, source, output_dir, from_email, min_score)


def _staging_post_run(vers_staging, resultat, source, output_dir, from_email, min_score):
    if not vers_staging:
        return
    from .staging_instantly import stager_leads_aper

    res_stg = stager_leads_aper(
        resultat.leads,
        secteur=source,
        session_id=output_dir.name,
        from_email=from_email,
        min_score=min_score,
    )
    console.print(
        f"\n[green]✓ Staging cold-mail créé : {res_stg.staging_id}[/green]\n"
        f"  Leads stagés (à valider) : {res_stg.nb_stages}\n"
        f"  Écartés (sans email)     : {res_stg.nb_sans_email}\n"
        f"  Écartés (sous le seuil)  : {res_stg.nb_sous_seuil}\n"
        f"  → Valider : [cyan]cold-mail show {res_stg.staging_id}[/cyan] "
        f"puis [cyan]cold-mail validate / send[/cyan]"
    )


@aper_group.command(name="geo")
@click.option("--bbox", required=True,
              help="Boîte géographique 'sud,ouest,nord,est' (degrés). "
                   "Ex. '50.40,2.80,50.55,2.95' (bassin de Lens).")
@click.option("--out", "out_path", type=click.Path(dir_okay=False, path_type=Path),
              required=True, help="CSV d'inventaire à générer (consommable par `aper run`).")
@click.option("--surface-min", "surface_min", type=float, default=None,
              help="Seuil bas de surface m² (défaut 1500 = seuil légal APER).")
@click.option("--surface-max", "surface_max", type=float, default=None,
              help="Plafond de surface m² (défaut : aucun). Ex. 1250 ≈ 50 places "
                   "pour cibler les petits parkings 'flotte'.")
@click.option("--dry-run", is_flag=True,
              help="Données OSM simulées, aucun appel réseau (test du flux).")
def aper_geo(
    bbox: str, out_path: Path, surface_min: float | None,
    surface_max: float | None, dry_run: bool,
) -> None:
    """Génère un CSV d'inventaire parkings depuis OpenStreetMap (Overpass)."""
    from .connecteur_geo import (
        Bbox,
        OverpassClient,
        OverpassClientDryRun,
        OverpassError,
        ecrire_inventaire_csv,
        recuperer_parkings,
    )
    from .models import SEUIL_APER_M2

    try:
        boite = Bbox.depuis_str(bbox)
    except ValueError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(2) from e

    seuil = surface_min if surface_min is not None else SEUIL_APER_M2
    client = OverpassClientDryRun() if dry_run else OverpassClient()
    if dry_run:
        console.print("[yellow]⚠  Mode dry-run : parkings OSM simulés.[/yellow]")

    plafond_txt = f"{surface_max:.0f}" if surface_max is not None else "∞"
    console.print(
        f"[cyan]Overpass — bbox {boite.as_overpass()} "
        f"(fenêtre {seuil:.0f}–{plafond_txt} m²)…[/cyan]"
    )
    try:
        lignes = recuperer_parkings(
            boite, client=client, surface_min_m2=seuil, surface_max_m2=surface_max
        )
    except OverpassError as e:
        msg = str(e)
        if "allowlist" in msg.lower() or "host_not_allowed" in msg.lower():
            console.print(
                "[red]✗ Hôte Overpass bloqué par l'allowlist réseau.[/red]\n"
                "  Ajoute `overpass-api.de` aux domaines autorisés (nouvelle session), "
                "ou relance avec --dry-run."
            )
        else:
            console.print(f"[red]✗ Overpass KO : {msg}[/red]")
        raise SystemExit(1) from e

    ecrire_inventaire_csv(lignes, out_path)
    console.print(
        f"\n[green]✓ Inventaire généré : {out_path}[/green]\n"
        f"  Parkings dans la fenêtre {seuil:.0f}–{plafond_txt} m² : {len(lignes)}\n"
        f"  → Lancer : [cyan]aper run --fichier {out_path}[/cyan]"
    )


@aper_group.command(name="signal-parking")
@click.option("--leads", "leads_path", required=True,
              type=click.Path(exists=True, dir_okay=False, path_type=Path),
              help="CSV de leads (PME découvertes SIRENE-first) avec latitude/longitude.")
@click.option("--inventaire", "inventaire_path", required=True,
              type=click.Path(exists=True, dir_okay=False, path_type=Path),
              help="CSV d'inventaire parkings (produit par `aper geo`).")
@click.option("--out", "out_path", required=True,
              type=click.Path(dir_okay=False, path_type=Path),
              help="CSV de sortie : leads annotés du signal parking.")
@click.option("--rayon-m", type=float, default=None,
              help="Rayon de rattachement PME↔parking en mètres (défaut 80).")
def aper_signal_parking(
    leads_path: Path, inventaire_path: Path, out_path: Path, rayon_m: float | None,
) -> None:
    """Annote des leads PME du SIGNAL parking (couche qualité du mix).

    Jointure spatiale GRATUITE : pour chaque PME (lat/lon), cherche un petit
    parking privé qualifiant (250-1250 m²) à proximité immédiate. Ajoute les
    colonnes signal_parking / parking_surface_m2 / parking_distance_m, et trie
    les leads « avec parking » en tête (priorisation avant enrichissement payant).
    """
    import csv

    from .parser_parkings import lire_csv_parkings
    from .signal_parking import SIGNAL_RAYON_M, LeadGeo, annoter_signal_parking

    parkings = lire_csv_parkings(inventaire_path).lignes
    with leads_path.open(encoding="utf-8-sig") as fh:
        lignes_leads = list(csv.DictReader(fh))
    if not lignes_leads:
        console.print("[red]✗ CSV de leads vide.[/red]")
        raise SystemExit(2)

    def _f(v: str | None) -> float | None:
        try:
            return float(v) if v not in (None, "") else None
        except ValueError:
            return None

    def _cle(row: dict[str, str], i: int) -> str:
        return (row.get("siren") or row.get("place_id") or f"row{i}").strip()

    leads_geo = [
        LeadGeo(cle=_cle(r, i), latitude=_f(r.get("latitude")), longitude=_f(r.get("longitude")))
        for i, r in enumerate(lignes_leads)
    ]
    rayon = rayon_m if rayon_m is not None else SIGNAL_RAYON_M
    resultats = annoter_signal_parking(leads_geo, parkings, rayon_m=rayon)

    # Annotation + tri (parking qualifiant en tête, puis distance croissante).
    enrichis: list[dict[str, str]] = []
    nb_quali = 0
    for i, row in enumerate(lignes_leads):
        res = resultats.get(_cle(row, i))
        quali = bool(res and res.qualifiant)
        nb_quali += int(quali)
        row = dict(row)
        row["signal_parking"] = "oui" if quali else "non"
        row["parking_surface_m2"] = f"{res.surface_m2:.0f}" if quali and res.surface_m2 else ""
        row["parking_distance_m"] = f"{res.distance_m:.0f}" if quali and res.distance_m else ""
        enrichis.append(row)
    enrichis.sort(
        key=lambda r: (r["signal_parking"] != "oui", _f(r.get("parking_distance_m")) or 1e9)
    )

    fieldnames = list(lignes_leads[0].keys()) + [
        c for c in ("signal_parking", "parking_surface_m2", "parking_distance_m")
        if c not in lignes_leads[0]
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(enrichis)

    console.print(
        f"\n[green]✓ Signal parking annoté : {out_path}[/green]\n"
        f"  Leads             : {len(enrichis)}\n"
        f"  Avec parking privé qualifiant (≤ {rayon:.0f} m) : {nb_quali}\n"
        f"  → Prioriser ces {nb_quali} leads pour l'enrichissement Dropcontact."
    )
