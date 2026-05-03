"""Maillage géographique — génère une grille de points GPS couvrant une zone.

Logique :
- Pour un département, on récupère sa bbox (sud-ouest / nord-est)
- On génère une grille de points espacés de `pas_grille_km`
- Chaque point sera utilisé comme centre d'un cercle de rayon `rayon_par_point_km`
  pour le Nearby Search Google Places.

Approximation : 1° de latitude ≈ 111 km, 1° de longitude varie selon la latitude.
Précision suffisante pour le calcul d'une grille (pas géodésique).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..models import Zone
from .referentiel_geo import bbox_departement


@dataclass(frozen=True)
class PointGrille:
    latitude: float
    longitude: float
    rayon_km: float
    label: str = ""


def _km_to_lat_degrees(km: float) -> float:
    """1° de latitude ≈ 111 km."""
    return km / 111.0


def _km_to_lng_degrees(km: float, latitude_deg: float) -> float:
    """1° de longitude = 111 km × cos(latitude)."""
    cos_lat = math.cos(math.radians(latitude_deg))
    if abs(cos_lat) < 0.01:  # éviter div par 0 près des pôles
        cos_lat = 0.01
    return km / (111.0 * cos_lat)


def grille_pour_bbox(
    sw_lat: float,
    sw_lng: float,
    ne_lat: float,
    ne_lng: float,
    pas_km: float,
    rayon_km: float,
    label_prefix: str = "",
) -> list[PointGrille]:
    """Génère une grille couvrante de points GPS dans la bbox.

    Le pas est calculé en latitude (constant) et en longitude (variable selon lat).
    """
    if sw_lat >= ne_lat or sw_lng >= ne_lng:
        raise ValueError(f"Bbox invalide : SW({sw_lat},{sw_lng}) doit être < NE({ne_lat},{ne_lng})")

    points: list[PointGrille] = []

    pas_lat_deg = _km_to_lat_degrees(pas_km)
    lat = sw_lat
    row = 0

    while lat <= ne_lat:
        # Pas en longitude recalculé à cette latitude (déformation Mercator)
        pas_lng_deg = _km_to_lng_degrees(pas_km, lat)
        lng = sw_lng
        col = 0
        while lng <= ne_lng:
            points.append(
                PointGrille(
                    latitude=round(lat, 5),
                    longitude=round(lng, 5),
                    rayon_km=rayon_km,
                    label=f"{label_prefix}r{row}c{col}" if label_prefix else f"r{row}c{col}",
                )
            )
            lng += pas_lng_deg
            col += 1
        lat += pas_lat_deg
        row += 1

    return points


def grille_pour_zone(zone: Zone) -> list[PointGrille]:
    """Génère la grille pour une `Zone` de config.

    Aujourd'hui supporte : type='departement' (codes INSEE).
    À étendre pour ville/region/france dans des versions ultérieures.
    """
    if zone.type != "departement":
        raise NotImplementedError(
            f"Type de zone '{zone.type}' pas encore supporté. "
            "Utilisez 'departement' avec un code INSEE."
        )

    points_globaux: list[PointGrille] = []

    for code in zone.codes:
        bbox = bbox_departement(code)
        if bbox is None:
            raise ValueError(f"Département inconnu : '{code}'. Codes valides : 01-95, 2A, 2B.")
        _, _, sw_lat, sw_lng, ne_lat, ne_lng = bbox
        pts = grille_pour_bbox(
            sw_lat=sw_lat,
            sw_lng=sw_lng,
            ne_lat=ne_lat,
            ne_lng=ne_lng,
            pas_km=zone.pas_grille_km,
            rayon_km=zone.rayon_par_point_km,
            label_prefix=f"dpt{code}_",
        )
        points_globaux.extend(pts)

    return points_globaux
