"""Connecteur IGN : surface d'emprise bâtie (toiture) via WFS BD TOPO.

Open data, gratuit. On interroge la couche bâtiments autour d'un point et on
calcule l'aire (m²) du polygone qui contient le point — proxy précis de la
surface de toiture, en complément de l'estimation Claude Vision.

Tolérant : toute panne réseau / format renvoie None (l'analyse reste possible
via la seule estimation Vision).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from ..common.logger import get_logger

logger = get_logger(__name__)

_WFS = "https://data.geopf.fr/wfs/ows"
_LAYER = "BDTOPO_V3:batiment"
_M_PAR_DEG_LAT = 110540.0


def _m_par_deg_lon(lat: float) -> float:
    return 111320.0 * math.cos(math.radians(lat))


def _aire_polygone_m2(anneau: list[list[float]], lat0: float) -> float:
    """Aire d'un anneau [[lon,lat],...] projeté localement, en m² (shoelace)."""
    kx, ky = _m_par_deg_lon(lat0), _M_PAR_DEG_LAT
    pts = [((lon) * kx, (lat) * ky) for lon, lat in anneau]
    s = 0.0
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def _point_dans_anneau(lat: float, lon: float, anneau: list[list[float]]) -> bool:
    """Ray casting sur un anneau [[lon,lat],...]."""
    dedans = False
    n = len(anneau)
    j = n - 1
    for i in range(n):
        loni, lati = anneau[i][0], anneau[i][1]
        lonj, latj = anneau[j][0], anneau[j][1]
        if ((lati > lat) != (latj > lat)) and (
            lon < (lonj - loni) * (lat - lati) / ((latj - lati) or 1e-12) + loni
        ):
            dedans = not dedans
        j = i
    return dedans


def _anneaux_exterieurs(geom: dict[str, Any]) -> list[list[list[float]]]:
    """Renvoie la liste des anneaux extérieurs (Polygon / MultiPolygon)."""
    t = geom.get("type")
    coords = geom.get("coordinates") or []
    if t == "Polygon" and coords:
        return [coords[0]]
    if t == "MultiPolygon":
        return [poly[0] for poly in coords if poly]
    return []


def surface_batie_depuis_geojson(
    lat: float, lon: float, geojson: dict[str, Any]
) -> float | None:
    """Aire (m²) du bâtiment contenant le point ; sinon le plus grand du lot."""
    candidats: list[tuple[bool, float]] = []
    for feat in geojson.get("features") or []:
        for anneau in _anneaux_exterieurs(feat.get("geometry") or {}):
            if len(anneau) < 4:
                continue
            aire = _aire_polygone_m2(anneau, lat)
            candidats.append((_point_dans_anneau(lat, lon, anneau), aire))
    if not candidats:
        return None
    contenants = [a for dedans, a in candidats if dedans]
    if contenants:
        return round(max(contenants), 1)
    # Repli : le plus grand bâtiment de la fenêtre (le point peut tomber dans la cour).
    return round(max(a for _, a in candidats), 1)


def _fetch_wfs(lat: float, lon: float, demi_cote_m: float = 70.0) -> dict[str, Any]:
    import requests

    dlat = demi_cote_m / _M_PAR_DEG_LAT
    dlon = demi_cote_m / _m_par_deg_lon(lat)
    # WFS 2.0 + EPSG:4326 → ordre BBOX lat,lon.
    bbox = f"{lat - dlat},{lon - dlon},{lat + dlat},{lon + dlon},EPSG:4326"
    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": _LAYER,
        "SRSNAME": "EPSG:4326",
        "BBOX": bbox,
        "OUTPUTFORMAT": "application/json",
        "COUNT": "30",
    }
    resp = requests.get(_WFS, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def surface_batie_m2(
    lat: float,
    lon: float,
    fetch: Callable[[float, float], dict[str, Any]] | None = None,
) -> float | None:
    """Surface d'emprise bâtie (m²) au point, ou None si indisponible.

    `fetch` est injectable pour les tests ; par défaut interroge le WFS IGN.
    """
    try:
        geojson = (fetch or _fetch_wfs)(lat, lon)
        return surface_batie_depuis_geojson(lat, lon, geojson)
    except Exception as exc:  # noqa: BLE001 — connecteur tolérant
        logger.warning("IGN emprise bâtie indisponible (%s)", exc)
        return None


__all__ = ["surface_batie_depuis_geojson", "surface_batie_m2"]
