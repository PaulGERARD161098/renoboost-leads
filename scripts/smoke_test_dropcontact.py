#!/usr/bin/env python3
"""Smoke-test minimal de l'API Dropcontact (L3.5).

Envoie 1 seul lead réel à Dropcontact et attend le résultat. Sert à vérifier
de bout en bout : clé API + accès réseau (allowlist) + POST /batch + polling.

Coût : ~0,50 € (1 lead facturé).

Usage :
    DROPCONTACT_API_KEY=... python scripts/smoke_test_dropcontact.py

Sortie : code retour 0 si l'API répond avec succès, 1 sinon (avec diagnostic).
"""

from __future__ import annotations

import json
import os
import sys

from renoboost_leads.stage3_5_enrichment.client import (
    DropcontactClient,
    DropcontactClientConfig,
    DropcontactError,
    DropcontactTimeoutError,
    lead_payload_dropcontact,
)


def main() -> int:
    key = os.environ.get("DROPCONTACT_API_KEY")
    if not key:
        print("ERREUR : variable d'environnement DROPCONTACT_API_KEY absente.")
        return 1
    print(f"Clé API présente (longueur {len(key)}).")

    cfg = DropcontactClientConfig(
        api_key=key,
        poll_initial_delay_s=8.0,
        poll_interval_s=8.0,
        poll_timeout_s=180.0,
    )
    client = DropcontactClient(cfg)

    lead = lead_payload_dropcontact(
        first_name=None,
        last_name=None,
        company="Dropcontact",
        website="dropcontact.com",
        siren=None,
    )
    print(f"Host appelé : {cfg.base_url}")
    print(f"Payload     : {lead}")

    try:
        resp = client.enrichir_batch([lead])
    except DropcontactError as e:
        # Couvre aussi le 403 'Host not in allowlist' (mismatch de domaine).
        print(f"ÉCHEC Dropcontact : {e}")
        if "allowlist" in str(e).lower():
            print(
                "→ Le host n'est pas autorisé par la politique réseau de "
                "l'environnement. Vérifie que 'api.dropcontact.com' figure "
                "dans les domaines autorisés (et relance une NOUVELLE session)."
            )
        return 1
    except DropcontactTimeoutError as e:
        print(f"TIMEOUT Dropcontact : {e}")
        return 1

    print(f"SUCCÈS — request_id : {resp.request_id}")
    print(f"Items reçus : {len(resp.data)}")
    print(f"Coût estimé : {resp.cout_eur:.2f} €")
    print(json.dumps(resp.data, indent=2, ensure_ascii=False)[:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
