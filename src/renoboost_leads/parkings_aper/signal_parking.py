"""Jointure « signal parking » — couche QUALITÉ du mix (incrément 3).

Inverse la logique de la Phase C : au lieu de partir d'un parking pour deviner
l'entreprise (forte attrition), on part des PME découvertes en SIRENE-first
(données complètes) et on VÉRIFIE laquelle possède un petit parking privé
qualifiant à proximité immédiate. Le parking devient un SIGNAL de priorisation,
pas la graine de découverte.

Fonction cœur PURE (aucun réseau) : on lui passe les leads (avec lat/lon) et un
inventaire de parkings (produit par `aper geo`), elle annote chaque lead. Le
fetch de l'inventaire reste à l'appelant (CLI) → testable sans I/O.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..common.logger import get_logger
from .models import LigneParking

logger = get_logger(__name__)

# Fenêtre de surface « petit parking privé » (≈ 10-50 places à 25 m²/place).
SIGNAL_SURFACE_MIN_M2 = 250.0
SIGNAL_SURFACE_MAX_M2 = 1250.0
# Rayon de rattachement PME ↔ parking : un parking PRIVÉ est adjacent au site.
SIGNAL_RAYON_M = 80.0


@dataclass
class LeadGeo:
    """Vue minimale d'un lead pour la jointure : identité + coordonnées."""

    cle: str  # identifiant stable (siren ou place_id) pour tracer
    latitude: float | None
    longitude: float | None


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance haversine en mètres entre deux points lat/lon."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


@dataclass
class ResultatSignal:
    """Résultat de jointure pour un lead : parking qualifiant trouvé ou non."""

    qualifiant: bool
    surface_m2: float | None = None
    distance_m: float | None = None


def chercher_parking_qualifiant(
    lat: float,
    lon: float,
    parkings: list[LigneParking],
    *,
    rayon_m: float = SIGNAL_RAYON_M,
    surface_min_m2: float = SIGNAL_SURFACE_MIN_M2,
    surface_max_m2: float = SIGNAL_SURFACE_MAX_M2,
) -> ResultatSignal:
    """Cherche le parking de la fenêtre de surface le PLUS PROCHE dans le rayon.

    Retourne le meilleur (plus proche) parking dont la surface est dans la
    fenêtre [min, max] et la distance ≤ rayon ; sinon `qualifiant=False`.
    """
    # Pré-filtre grossier en degrés pour éviter le haversine sur tout l'inventaire.
    # 0,002° ≈ 220 m de marge autour du rayon (large, sans risque de rater).
    marge = 0.002 + rayon_m / 111_000.0
    meilleur: ResultatSignal = ResultatSignal(qualifiant=False)
    for p in parkings:
        if p.latitude is None or p.longitude is None:
            continue
        if abs(p.latitude - lat) > marge or abs(p.longitude - lon) > marge:
            continue
        if not (surface_min_m2 <= p.surface_m2 <= surface_max_m2):
            continue
        d = distance_m(lat, lon, p.latitude, p.longitude)
        if d > rayon_m:
            continue
        if not meilleur.qualifiant or (
            meilleur.distance_m is not None and d < meilleur.distance_m
        ):
            meilleur = ResultatSignal(qualifiant=True, surface_m2=p.surface_m2, distance_m=d)
    return meilleur


def annoter_signal_parking(
    leads: list[LeadGeo],
    parkings: list[LigneParking],
    *,
    rayon_m: float = SIGNAL_RAYON_M,
    surface_min_m2: float = SIGNAL_SURFACE_MIN_M2,
    surface_max_m2: float = SIGNAL_SURFACE_MAX_M2,
) -> dict[str, ResultatSignal]:
    """Annote chaque lead avec son parking qualifiant éventuel (par `cle`).

    Returns:
        {cle_lead: ResultatSignal}. Les leads sans coordonnées sont absents.
    """
    resultats: dict[str, ResultatSignal] = {}
    nb_geo = nb_quali = 0
    for lead in leads:
        if lead.latitude is None or lead.longitude is None:
            continue
        nb_geo += 1
        res = chercher_parking_qualifiant(
            lead.latitude, lead.longitude, parkings,
            rayon_m=rayon_m, surface_min_m2=surface_min_m2, surface_max_m2=surface_max_m2,
        )
        resultats[lead.cle] = res
        if res.qualifiant:
            nb_quali += 1
    logger.info(
        "Signal parking : %d/%d leads géolocalisés ont un parking privé "
        "qualifiant (%.0f-%.0f m², ≤ %.0f m)",
        nb_quali, nb_geo, surface_min_m2, surface_max_m2, rayon_m,
    )
    return resultats


__all__ = [
    "LeadGeo",
    "ResultatSignal",
    "SIGNAL_RAYON_M",
    "SIGNAL_SURFACE_MAX_M2",
    "SIGNAL_SURFACE_MIN_M2",
    "annoter_signal_parking",
    "chercher_parking_qualifiant",
    "distance_m",
]
