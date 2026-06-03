#!/usr/bin/env python3
"""Ingestion des bornes de recharge VE dans Supabase (table `bornes_recharge`).

Source par défaut : fichier consolidé IRVE national (data.gouv.fr), mis à jour
quotidiennement. Réutilisable pour un export Rossini Energy suivant le même
schéma (option --source rossini --file/--url).

Principe : on télécharge une fois, on upsert en base ; les requêtes de proximité
se font ensuite localement (cf. web/lib/bornes.ts). Pas d'appel externe live.

Env requis :
  SUPABASE_URL                (ou NEXT_PUBLIC_SUPABASE_URL)
  SUPABASE_SERVICE_ROLE_KEY

Exemples :
  python scripts/ingest_bornes.py
  python scripts/ingest_bornes.py --source rossini --file export_rossini.csv
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import urllib.request

# Resource « fichier consolidé » IRVE (CSV) sur data.gouv.fr. Peut évoluer :
# surchargeable via --url.
IRVE_CSV_URL = "https://www.data.gouv.fr/fr/datasets/r/eb76d20a-8501-400e-b336-d85724de5435"

BATCH = 500


def _f(v: str | None) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def _i(v: str | None) -> int | None:
    try:
        return int(float(v)) if v not in (None, "") else None
    except ValueError:
        return None


def map_row(row: dict[str, str], source: str) -> dict | None:
    """Mappe une ligne IRVE (schéma statique 2.x consolidé) vers notre table."""
    lat = _f(row.get("consolidated_latitude") or row.get("latitude"))
    lng = _f(row.get("consolidated_longitude") or row.get("longitude"))
    # Repli : colonne coordonneesXY au format "[lon, lat]" ou "lon,lat".
    if (lat is None or lng is None) and row.get("coordonneesXY"):
        raw = row["coordonneesXY"].strip().strip("[]")
        parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
        if len(parts) == 2:
            lng, lat = _f(parts[0]), _f(parts[1])
    if lat is None or lng is None:
        return None

    cp = (row.get("consolidated_code_postal") or row.get("code_postal") or "").strip()
    dept = cp[:2] if len(cp) >= 2 else None
    source_id = (
        row.get("id_pdc_itinerance")
        or row.get("id_station_itinerance")
        or row.get("id_pdc_local")
        or None
    )
    return {
        "source": source,
        "source_id": source_id,
        "nom_station": row.get("nom_station") or None,
        "operateur": row.get("nom_operateur") or None,
        "amenageur": row.get("nom_amenageur") or None,
        "enseigne": row.get("nom_enseigne") or None,
        "lat": lat,
        "lng": lng,
        "puissance_kw": _f(row.get("puissance_nominale")),
        "nb_points": _i(row.get("nbre_pdc")),
        "adresse": row.get("adresse_station") or None,
        "code_postal": cp or None,
        "commune": row.get("consolidated_commune") or row.get("commune") or None,
        "departement": dept,
        "date_maj": (row.get("date_maj") or None),
    }


def upsert(base_url: str, key: str, rows: list[dict]) -> None:
    url = f"{base_url}/rest/v1/bornes_recharge?on_conflict=source,source_id"
    data = json.dumps(rows).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")  # noqa: S310
    req.add_header("apikey", key)
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Prefer", "resolution=merge-duplicates,return=minimal")
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        if resp.status >= 300:
            raise RuntimeError(f"Upsert HTTP {resp.status}: {resp.read()[:300]!r}")


def open_source(args: argparse.Namespace) -> io.TextIOBase:
    if args.file:
        return open(args.file, encoding="utf-8-sig", newline="")
    url = args.url or IRVE_CSV_URL
    print(f"Téléchargement : {url}", file=sys.stderr)
    # User-Agent explicite : data.gouv.fr refuse (403) les requêtes anonymes.
    req = urllib.request.Request(  # noqa: S310
        url, headers={"User-Agent": "renoboost-leads/1.0 (ingestion bornes IRVE)"}
    )
    raw = urllib.request.urlopen(req, timeout=300).read()  # noqa: S310
    return io.StringIO(raw.decode("utf-8-sig", errors="replace"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingestion bornes VE -> Supabase.")
    ap.add_argument("--source", default="irve", choices=["irve", "rossini", "chargemap"])
    ap.add_argument("--url", help="URL CSV (défaut: fichier consolidé IRVE).")
    ap.add_argument("--file", help="Fichier CSV local (au lieu de --url).")
    ap.add_argument("--dry-run", action="store_true", help="N'écrit rien, compte seulement.")
    args = ap.parse_args()

    base_url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not args.dry_run and (not base_url or not key):
        print("SUPABASE_URL et SUPABASE_SERVICE_ROLE_KEY requis.", file=sys.stderr)
        return 2

    reader = csv.DictReader(open_source(args), delimiter=";")
    # IRVE est en ';' ; si une seule colonne détectée, on retente en ','.
    if reader.fieldnames and len(reader.fieldnames) <= 1:
        f = open_source(args)
        reader = csv.DictReader(f, delimiter=",")

    batch: list[dict] = []
    total = ok = 0
    for row in reader:
        total += 1
        mapped = map_row(row, args.source)
        if not mapped:
            continue
        ok += 1
        batch.append(mapped)
        if len(batch) >= BATCH and not args.dry_run:
            upsert(base_url, key, batch)
            batch = []
    if batch and not args.dry_run:
        upsert(base_url, key, batch)

    print(f"Lignes lues: {total} · géolocalisées/insérées: {ok}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
