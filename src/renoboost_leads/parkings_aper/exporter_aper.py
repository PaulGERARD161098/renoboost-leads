"""Export CSV des LeadAper (étend l'exporter L4 avec colonnes APER)."""

from __future__ import annotations

from pathlib import Path

from ..common.logger import get_logger
from ..exporter import COLONNES_STAGE4, _ecrire_csv
from ..models import LeadAper

logger = get_logger(__name__)


COLONNES_APER_EXTRA = [
    "source_aper",
    "date_run_aper",
    "identifiant_parking",
    "surface_parking_m2",
    "surface_ombrable_m2",
    "nb_places_estime",
    "echeance_aper",
    "priorite_aper",
    "deja_vu_parking",
]


# Colonnes « métier » en tête de CSV pour lecture humaine rapide.
_EN_TETE = [
    "nom",
    "siren",
    "surface_parking_m2",
    "echeance_aper",
    "priorite_aper",
    "score_interet",
    "top_lead",
    "raison_score",
    "pitch_propose",
]

COLONNES_APER = _EN_TETE + [
    c for c in COLONNES_STAGE4 + COLONNES_APER_EXTRA if c not in set(_EN_TETE)
]


def export_aper_csv(leads: list[LeadAper], output_path: Path) -> Path:
    """Écrit un CSV APER (toutes colonnes L1+L2+L3+L4+aper)."""
    rows = [lead.model_dump() for lead in leads]
    p = _ecrire_csv(rows, COLONNES_APER, output_path)
    logger.info("CSV parkings APER écrit : %s (%d leads)", p, len(leads))
    return p
