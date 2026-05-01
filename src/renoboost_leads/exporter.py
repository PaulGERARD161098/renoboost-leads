"""Export CSV des leads."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from .common.logger import get_logger
from .models import LeadStage1, RunStats

logger = get_logger(__name__)


# Ordre des colonnes pour le CSV étage 1
COLONNES_STAGE1 = [
    "place_id",
    "nom",
    "adresse",
    "ville",
    "code_postal",
    "pays",
    "telephone",
    "site_web",
    "note",
    "nb_avis",
    "type_principal",
    "types",
    "statut_business",
    "niveau_prix",
    "latitude",
    "longitude",
    "google_maps_url",
    "secteur_recherche",
    "requete_origine",
    "extraction_date",
]


def export_stage1_csv(leads: list[LeadStage1], output_path: Path) -> Path:
    """Écrit les leads dans un CSV (séparateur virgule, encodage utf-8-sig pour Excel FR)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLONNES_STAGE1, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()

        for lead in leads:
            row = lead.model_dump()
            # Conversions pour CSV
            row["types"] = "|".join(row.get("types") or [])
            row["extraction_date"] = (
                row["extraction_date"].isoformat() if row.get("extraction_date") else ""
            )
            # Filtre les colonnes au schéma
            writer.writerow({k: row.get(k, "") for k in COLONNES_STAGE1})

    logger.info("CSV étage 1 écrit : %s (%d leads)", output_path, len(leads))
    return output_path


def export_run_stats(stats: RunStats, output_path: Path) -> Path:
    """Sérialise les stats du run en JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(stats.model_dump(mode="json"), fh, ensure_ascii=False, indent=2, default=str)
    return output_path


def generer_registre_rgpd(
    output_path: Path,
    client_name: str,
    nb_leads: int,
    sources: list[str],
) -> Path:
    """Génère le registre RGPD du run (article 30)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    contenu = f"""# Registre des traitements — Run RénoBoost Leads

**Date** : {datetime.now().isoformat()}
**Client / Campagne** : {client_name}
**Nombre de leads collectés** : {nb_leads}

## Sources des données
{chr(10).join(f'- {s}' for s in sources)}

## Finalité du traitement
Prospection commerciale B2B (article 6.1.f RGPD — intérêt légitime).

## Catégories de personnes concernées
- Personnes morales (entreprises, établissements)
- Le cas échéant, contacts professionnels génériques (`contact@`, `direction@`)

## Catégories de données traitées
- Identification entreprise (raison sociale, adresse, téléphone, site web)
- Métadonnées Google Places (note, nb avis, catégories)
- Données légales (SIREN, NAF, dirigeants) — si étage 2 activé
- Emails professionnels — si étage 3 activé

## Durée de conservation
3 ans à compter du dernier contact, conformément aux recommandations CNIL pour la prospection B2B.

## Mesures de sécurité
- Données stockées en local, pas de transmission vers des tiers non autorisés
- Clés API en variables d'environnement (jamais en clair dans le code)
- Restriction par adresses IP des accès aux APIs

## Droits des personnes
Toute personne dont les données figurent dans ce fichier peut exercer ses droits
(accès, rectification, effacement, opposition) en contactant le responsable de traitement.
"""
    output_path.write_text(contenu, encoding="utf-8")
    return output_path
