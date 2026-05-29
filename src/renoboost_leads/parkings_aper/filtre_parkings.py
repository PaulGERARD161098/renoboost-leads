"""Filtre des parkings soumis à l'obligation loi APER (surface > seuil)."""

from __future__ import annotations

from ..common.logger import get_logger
from .models import AperConfig, LigneParking

logger = get_logger(__name__)


def filtrer_parkings(
    lignes: list[LigneParking], config: AperConfig | None = None
) -> tuple[list[LigneParking], dict[str, int]]:
    """Conserve les parkings dont la surface ≥ `surface_min_m2`.

    Returns:
        (lignes_retenues, rejets) où `rejets` compte les motifs d'exclusion.
    """
    config = config or AperConfig()
    retenues: list[LigneParking] = []
    rejets: dict[str, int] = {"surface_insuffisante": 0}

    for ligne in lignes:
        if ligne.surface_m2 < config.surface_min_m2:
            rejets["surface_insuffisante"] += 1
            continue
        retenues.append(ligne)

    logger.info(
        "Filtre APER : %d/%d parkings retenus (seuil %.0f m²)",
        len(retenues),
        len(lignes),
        config.surface_min_m2,
    )
    return retenues, rejets
