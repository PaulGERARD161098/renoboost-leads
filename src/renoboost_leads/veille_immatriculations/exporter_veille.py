"""Export CSV des LeadVeille (étend l'exporter L4 avec colonnes veille)."""

from __future__ import annotations

from pathlib import Path

from ..common.logger import get_logger
from ..exporter import COLONNES_STAGE4, _ecrire_csv
from ..models import LeadVeille

logger = get_logger(__name__)


COLONNES_VEILLE_EXTRA = [
    "source_veille",
    "date_run_veille",
    "date_immatriculation_ve",
    "marque_ve",
    "modele_ve",
    "energie_ve",
    "type_vehicule_ve",
    "deja_eu_ve",
    "premiere_date_ve",
]


# Mis en évidence en début de CSV pour lecture humaine rapide
COLONNES_VEILLE = (
    ["nom", "siren", "score_interet", "top_lead", "deja_eu_ve"]
    + ["date_immatriculation_ve", "marque_ve", "modele_ve", "energie_ve"]
    + ["raison_score", "pitch_propose"]
    + [
        c
        for c in COLONNES_STAGE4 + COLONNES_VEILLE_EXTRA
        if c
        not in {
            "nom",
            "siren",
            "score_interet",
            "top_lead",
            "deja_eu_ve",
            "date_immatriculation_ve",
            "marque_ve",
            "modele_ve",
            "energie_ve",
            "raison_score",
            "pitch_propose",
        }
    ]
)


def export_veille_csv(leads: list[LeadVeille], output_path: Path) -> Path:
    """Écrit un CSV veille (toutes colonnes L1+L2+L3+L4+veille)."""
    rows = [lead.model_dump() for lead in leads]
    p = _ecrire_csv(rows, COLONNES_VEILLE, output_path)
    logger.info("CSV veille écrit : %s (%d leads)", p, len(leads))
    return p
