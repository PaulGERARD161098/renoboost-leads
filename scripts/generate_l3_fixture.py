#!/usr/bin/env python3
"""Génère une fixture L3 de 5 leads variés pour le smoke test L4 réel.

Usage :
    python scripts/generate_l3_fixture.py [--target <path>]

Sans argument : crée
`data/output/2026-05-13_KEYR_premier-test/etage3_contacts.csv` (chemin attendu
par `scripts/premier_test_l4.sh`).

Les 5 leads couvrent un spectre volontairement varié pour que Claude ait
de quoi différencier les scores :
- 1 cabinet médical avec dirigeant + email vérifié (cible plausible RénoBoost)
- 1 PME industrielle (cible moyenne)
- 1 bureau d'études énergétiques (cible top)
- 1 restaurant (cible faible — RénoBoost ne cible pas les restos)
- 1 chaîne hôtelière flaguée (cible faible — pas de dirigeant local)
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

# Permet l'exécution sans `pip install -e .` (utile pour le script).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from renoboost_leads.exporter import COLONNES_STAGE3  # noqa: E402

DEFAULT_TARGET = Path("data/output/2026-05-13_KEYR_premier-test/etage3_contacts.csv")

_NOW_ISO = datetime.now(timezone.utc).isoformat()

LEADS_FIXTURE: list[dict[str, str]] = [
    {
        "place_id": "FIX_001",
        "nom": "Cabinet Médical du Nord",
        "adresse": "12 rue de la Liberté",
        "ville": "Lille",
        "code_postal": "59000",
        "telephone": "03 20 12 34 56",
        "site_web": "https://cabinet-medical-nord.fr",
        "note": "4.6",
        "nb_avis": "82",
        "type_principal": "doctor",
        "secteur_recherche": "cabinet médical",
        "siren": "521789456",
        "code_naf": "86.21Z",
        "libelle_naf": "Activité des médecins généralistes",
        "forme_juridique": "SCP",
        "statut_actif": "True",
        "tranche_effectif": "12",
        "libelle_effectif": "10 à 19 salariés",
        "dirigeant_nom": "Dupont",
        "dirigeant_prenom": "Marie",
        "dirigeant_qualite": "Gérante",
        "emails_verifies": "contact@cabinet-medical-nord.fr",
        "emails_candidats": "marie.dupont@cabinet-medical-nord.fr",
        "domaine_extrait": "cabinet-medical-nord.fr",
        "nb_emails_verifies": "1",
        "nb_emails_candidats": "1",
        "source_globale": "scraping_et_patterns",
        "contient_dirigeant_pattern": "VRAI",
    },
    {
        "place_id": "FIX_002",
        "nom": "Atelier Méca Roubaix",
        "adresse": "47 boulevard Industriel",
        "ville": "Roubaix",
        "code_postal": "59100",
        "telephone": "03 20 75 22 11",
        "site_web": "https://meca-roubaix.fr",
        "note": "4.2",
        "nb_avis": "31",
        "type_principal": "establishment",
        "secteur_recherche": "atelier mécanique",
        "siren": "412556789",
        "code_naf": "25.62B",
        "libelle_naf": "Mécanique industrielle",
        "forme_juridique": "SARL",
        "statut_actif": "True",
        "tranche_effectif": "21",
        "libelle_effectif": "20 à 49 salariés",
        "dirigeant_nom": "Lefebvre",
        "dirigeant_prenom": "Jean",
        "dirigeant_qualite": "Gérant",
        "emails_verifies": "",
        "emails_candidats": "contact@meca-roubaix.fr|direction@meca-roubaix.fr",
        "domaine_extrait": "meca-roubaix.fr",
        "nb_emails_verifies": "0",
        "nb_emails_candidats": "2",
        "source_globale": "patterns_uniquement",
        "contient_dirigeant_pattern": "FAUX",
    },
    {
        "place_id": "FIX_003",
        "nom": "EnergieConseil BE",
        "adresse": "3 place de la République",
        "ville": "Tourcoing",
        "code_postal": "59200",
        "telephone": "03 20 88 44 33",
        "site_web": "https://energieconseil-be.fr",
        "note": "4.8",
        "nb_avis": "47",
        "type_principal": "establishment",
        "secteur_recherche": "bureau d'études énergétiques",
        "siren": "789456123",
        "code_naf": "71.12B",
        "libelle_naf": "Ingénierie, études techniques",
        "forme_juridique": "SAS",
        "statut_actif": "True",
        "tranche_effectif": "22",
        "libelle_effectif": "20 à 49 salariés",
        "dirigeant_nom": "Moreau",
        "dirigeant_prenom": "Sophie",
        "dirigeant_qualite": "Présidente",
        "emails_verifies": "sophie.moreau@energieconseil-be.fr|contact@energieconseil-be.fr",
        "emails_candidats": "",
        "domaine_extrait": "energieconseil-be.fr",
        "nb_emails_verifies": "2",
        "nb_emails_candidats": "0",
        "source_globale": "scraping_uniquement",
        "contient_dirigeant_pattern": "VRAI",
    },
    {
        "place_id": "FIX_004",
        "nom": "Le Bistrot du Coin",
        "adresse": "5 grand-place",
        "ville": "Lille",
        "code_postal": "59000",
        "telephone": "03 20 55 66 77",
        "site_web": "",
        "note": "4.0",
        "nb_avis": "215",
        "type_principal": "restaurant",
        "secteur_recherche": "restaurant",
        "siren": "352147896",
        "code_naf": "56.10A",
        "libelle_naf": "Restauration traditionnelle",
        "forme_juridique": "SARL",
        "statut_actif": "True",
        "tranche_effectif": "11",
        "libelle_effectif": "10 à 19 salariés",
        "emails_verifies": "",
        "emails_candidats": "",
        "nb_emails_verifies": "0",
        "nb_emails_candidats": "0",
        "source_globale": "aucun_email",
        "contient_dirigeant_pattern": "FAUX",
    },
    {
        "place_id": "FIX_005",
        "nom": "Ibis Lille Centre",
        "adresse": "29 avenue Charles Saint-Venant",
        "ville": "Lille",
        "code_postal": "59000",
        "telephone": "03 28 36 30 30",
        "site_web": "https://all.accor.com/hotel/0901/index.fr.shtml",
        "note": "4.1",
        "nb_avis": "1820",
        "type_principal": "lodging",
        "secteur_recherche": "hôtel",
        "siren": "542048574",
        "code_naf": "55.10Z",
        "libelle_naf": "Hôtels et hébergement similaire",
        "forme_juridique": "SA",
        "statut_actif": "True",
        "tranche_effectif": "32",
        "libelle_effectif": "100 à 199 salariés",
        "flag_chaine": "True",
        "note_chaine": "Marque Accor — pas de dirigeant local",
        "emails_verifies": "",
        "emails_candidats": "",
        "nb_emails_verifies": "0",
        "nb_emails_candidats": "0",
        "source_globale": "chaine_non_traitee",
        "contient_dirigeant_pattern": "FAUX",
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        default=DEFAULT_TARGET,
        help=f"Chemin du CSV à créer (défaut : {DEFAULT_TARGET})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Écrase la fixture existante.",
    )
    args = parser.parse_args()

    if args.target.exists() and not args.force:
        print(f"✓ Fixture déjà présente : {args.target}")
        print("  (passe --force pour réécrire)")
        return 0

    args.target.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    for lead in LEADS_FIXTURE:
        row = dict.fromkeys(COLONNES_STAGE3, "")
        row.update(lead)
        if not row.get("extraction_date"):
            row["extraction_date"] = _NOW_ISO
        rows.append(row)

    with args.target.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLONNES_STAGE3)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✓ Fixture L3 créée : {args.target}")
    print(f"  → {len(rows)} leads variés prêts pour smoke test L4")
    return 0


if __name__ == "__main__":
    sys.exit(main())
