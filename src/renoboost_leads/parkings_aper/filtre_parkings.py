"""Filtre des parkings soumis à l'obligation loi APER (surface > seuil)."""

from __future__ import annotations

from ..common.logger import get_logger
from .models import AperConfig, LigneParking

logger = get_logger(__name__)


def filtrer_parkings(
    lignes: list[LigneParking], config: AperConfig | None = None
) -> tuple[list[LigneParking], dict[str, int]]:
    """Conserve les parkings dont la surface est dans la fenêtre configurée.

    Fenêtre : `surface_min_m2` ≤ surface ≤ `surface_max_m2` (plafond optionnel,
    None = pas de plafond). Le plafond sert à cibler les petits parkings
    « flotte » et à écarter les très grands parcs (hyper, ZC).

    Returns:
        (lignes_retenues, rejets) où `rejets` compte les motifs d'exclusion.
    """
    config = config or AperConfig()
    retenues: list[LigneParking] = []
    rejets: dict[str, int] = {"surface_insuffisante": 0, "surface_excessive": 0}

    for ligne in lignes:
        if ligne.surface_m2 < config.surface_min_m2:
            rejets["surface_insuffisante"] += 1
            continue
        if config.surface_max_m2 is not None and ligne.surface_m2 > config.surface_max_m2:
            rejets["surface_excessive"] += 1
            continue
        retenues.append(ligne)

    plafond = (
        f"{config.surface_max_m2:.0f}" if config.surface_max_m2 is not None else "∞"
    )
    logger.info(
        "Filtre APER : %d/%d parkings retenus (fenêtre %.0f–%s m²)",
        len(retenues),
        len(lignes),
        config.surface_min_m2,
        plafond,
    )
    return retenues, rejets
