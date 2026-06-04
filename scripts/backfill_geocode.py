#!/usr/bin/env python3
"""Backfill du géocodage des leads (latitude/longitude) via la BAN.

Sans coordonnées, un lead n'a ni analyse satellite (score foncier) ni
« bornes à proximité ». Ce script repère les leads dépourvus de lat/lng mais
disposant d'une adresse, les géocode via la Base Adresse Nationale, et met à
jour Supabase. Idempotent : ne touche que les leads sans coordonnées.

Prérequis :
  - Variables d'env : SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
  - Réseau : `api-adresse.data.gouv.fr` doit être dans l'allowlist de
    l'environnement (sinon HTTP 403/refused — voir geocoder.py).

Usage :
  python scripts/backfill_geocode.py            # exécution réelle
  python scripts/backfill_geocode.py --dry-run  # simulation (aucune écriture)
  python scripts/backfill_geocode.py --limit 20 # borne le nombre de leads
"""

from __future__ import annotations

import argparse
import os
import sys

import requests

from renoboost_leads.common.rate_limiter import RateLimiter
from renoboost_leads.stage0_sirene_first.geocoder import (
    AdresseIntrouvableError,
    BANGeocoder,
    GeocodageError,
    GeocoderConfig,
)


def _env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        sys.exit(f"Variable d'environnement manquante : {name}")
    return val


def _adresse_complete(lead: dict) -> str:
    """Concatène adresse + code postal + ville pour maximiser le match BAN."""
    bouts = [lead.get("adresse"), lead.get("code_postal"), lead.get("ville")]
    return " ".join(b.strip() for b in bouts if b and b.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill géocodage des leads.")
    parser.add_argument("--dry-run", action="store_true", help="N'écrit rien.")
    parser.add_argument("--limit", type=int, default=0, help="Limite (0 = tous).")
    args = parser.parse_args()

    base = _env("SUPABASE_URL").rstrip("/")
    key = _env("SUPABASE_SERVICE_ROLE_KEY")
    rest = f"{base}/rest/v1/leads"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    # Leads sans coordonnées mais avec une adresse exploitable.
    params = {
        "select": "id,entreprise,adresse,code_postal,ville",
        "latitude": "is.null",
        "or": "(adresse.not.is.null,ville.not.is.null)",
    }
    if args.limit:
        params["limit"] = str(args.limit)
    resp = requests.get(rest, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    leads = resp.json()
    print(f"{len(leads)} lead(s) à géocoder.")
    if not leads:
        return

    geocoder = BANGeocoder(GeocoderConfig(rate_limiter=RateLimiter(40)))
    ok = skip = err = 0

    for lead in leads:
        adresse = _adresse_complete(lead)
        nom = lead.get("entreprise") or lead["id"]
        if not adresse:
            print(f"  · {nom} : pas d'adresse, ignoré.")
            skip += 1
            continue
        try:
            r = geocoder.geocoder(adresse)
        except AdresseIntrouvableError as e:
            print(f"  · {nom} : introuvable ({e}).")
            skip += 1
            continue
        except GeocodageError as e:
            print(f"  ✗ {nom} : erreur géocodage ({e}).")
            err += 1
            continue

        print(f"  ✓ {nom} : {r.latitude:.5f}, {r.longitude:.5f} (score {r.score:.2f})")
        if not args.dry_run:
            up = requests.patch(
                rest,
                headers={**headers, "Prefer": "return=minimal"},
                params={"id": f"eq.{lead['id']}"},
                json={"latitude": r.latitude, "longitude": r.longitude},
                timeout=30,
            )
            up.raise_for_status()
        ok += 1

    mode = " (dry-run)" if args.dry_run else ""
    print(f"\nTerminé{mode} : {ok} géocodés, {skip} ignorés, {err} erreurs.")


if __name__ == "__main__":
    main()
