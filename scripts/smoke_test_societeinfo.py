#!/usr/bin/env python3
"""Smoke-test RÉEL de l'API Societeinfo — 1 appel, valide clé + allowlist + mapping.

Valide de bout en bout, sur un SIREN connu :
  1. la clé `SOCIETEINFO_API_KEY` ;
  2. l'accès réseau (allowlist du proxy : `societeinfo.com`) ;
  3. le mapping `_parse_resultat` (affiche la réponse brute + le parsing).

⚠️ Pré-requis (à régler dans une NOUVELLE session — les changements d'allowlist /
d'env ne s'appliquent qu'aux sessions suivantes) :
  - ajouter `societeinfo.com` aux domaines autorisés de l'environnement ;
  - définir `SOCIETEINFO_API_KEY`.

Usage :
    python scripts/smoke_test_societeinfo.py [SIREN]
    # défaut : 552081317 (Société Générale) — remplace par un SIREN de ta cible.
"""

from __future__ import annotations

import json
import sys

from renoboost_leads.settings import get_settings
from renoboost_leads.societeinfo_enrichment.client import (
    SocieteinfoClient,
    SocieteinfoClientConfig,
    SocieteinfoError,
)

SIREN_DEFAUT = "552081317"  # Société Générale (entité bien documentée)


def main() -> int:
    siren = sys.argv[1] if len(sys.argv) > 1 else SIREN_DEFAUT
    settings = get_settings()

    if not settings.has_societeinfo():
        print("✗ SOCIETEINFO_API_KEY absente. Ajoute-la dans .env puis relance.")
        return 2

    client = SocieteinfoClient(
        SocieteinfoClientConfig(
            api_key=settings.societeinfo_api_key.get_secret_value(),
        )
    )

    print("→ Health-check Societeinfo (SIREN test)…")
    ok, msg = client.health_check()
    if not ok:
        if "allowlist" in msg.lower() or "host_not_allowed" in msg.lower():
            print(
                "✗ Hôte bloqué par l'allowlist réseau.\n"
                "  Ajoute `societeinfo.com` aux domaines autorisés de "
                "l'environnement, puis relance dans une NOUVELLE session."
            )
        else:
            print(f"✗ Health-check KO : {msg}")
        return 1
    print("  ✓ Connectivité + auth OK")

    print(f"→ Enrichissement réel SIREN={siren}…")
    try:
        res = client.enrichir(siren=siren)
    except SocieteinfoError as e:
        print(f"✗ Appel échoué : {e}")
        return 1

    print("\n=== Réponse parsée (ResultatSocieteinfo) ===")
    parsed = {
        "trouve": res.trouve,
        "siren": res.siren,
        "naf": res.naf,
        "libelle_naf": res.libelle_naf,
        "effectif": res.effectif,
        "chiffre_affaires": res.chiffre_affaires,
        "dirigeant": res.dirigeant,
        "email": res.email,
        "emails": res.emails,
        "telephone": res.telephone,
        "site_web": res.site_web,
        "linkedin": res.linkedin,
    }
    print(json.dumps(parsed, ensure_ascii=False, indent=2))

    print("\n=== Réponse BRUTE (à comparer au mapping _parse_resultat) ===")
    print(json.dumps(res.brut, ensure_ascii=False, indent=2)[:4000])

    if not res.trouve:
        print(
            "\n⚠ trouve=False : le mapping `_parse_resultat` ne reconnaît pas la "
            "forme de réponse de ton plan. Ajuste-le d'après la réponse brute ci-dessus."
        )
        return 1

    print("\n✓ Smoke-test réussi — mapping confirmé sur cette réponse.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
