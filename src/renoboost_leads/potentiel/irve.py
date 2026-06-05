"""Connecteur IRVE : bornes de recharge VE depuis le jeu consolidé data.gouv.

Open data, gratuit. Le fichier consolidé national (transport.data.gouv.fr) liste
les points de recharge avec coordonnées, puissance, opérateur. On le charge une
fois (cache process) puis on compte les bornes par rayon autour d'un point.

Tolérant : toute panne réseau / format renvoie une liste vide (analyse optionnelle).
"""

from __future__ import annotations

import csv
import io
import math
import os
from dataclasses import dataclass, field

from ..common.logger import get_logger

logger = get_logger(__name__)

# Fichier consolidé « IRVE statique » (data.gouv / transport.data.gouv.fr).
IRVE_URL_DEFAUT = (
    "https://www.data.gouv.fr/fr/datasets/r/eb76d20a-8501-400e-b336-d85724de5435"
)

_RAYON_TERRE_KM = 6371.0
_cache: dict[str, list[Borne]] = {}


@dataclass(frozen=True)
class Borne:
    lat: float
    lon: float
    puissance_kw: float | None = None
    operateur: str | None = None

    def type_label(self) -> str:
        p = self.puissance_kw
        if p is None:
            return "puissance n.c."
        if p >= 50:
            return f"rapide {int(p)} kW (DC)"
        if p > 22:
            return f"{int(p)} kW"
        return f"{int(p)} kW (AC)"


@dataclass
class ComptageBornes:
    sur_site: int = 0  # ≤ 150 m
    voisinage_1km: int = 0  # ≤ 1 km
    rayon_10km: int = 0  # ≤ 10 km
    types: list[str] = field(default_factory=list)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * _RAYON_TERRE_KM * math.asin(math.sqrt(a))


def _parse_coord(row: dict[str, str]) -> tuple[float, float] | None:
    """Extrait (lat, lon) d'une ligne IRVE, tolérant aux variantes de colonnes."""
    lat = row.get("consolidated_latitude") or row.get("ylatitude") or row.get("lat")
    lon = row.get("consolidated_longitude") or row.get("xlongitude") or row.get("lon")
    try:
        if lat and lon:
            return float(lat), float(lon)
    except (TypeError, ValueError):
        pass
    # Repli : champ "coordonneesXY" = "[lon, lat]".
    brut = row.get("coordonneesXY") or row.get("coordonnees")
    if brut:
        nums = brut.replace("[", "").replace("]", "").split(",")
        try:
            lon_v, lat_v = float(nums[0]), float(nums[1])
            return lat_v, lon_v
        except (IndexError, ValueError):
            return None
    return None


def _parse_rows(texte: str) -> list[Borne]:
    bornes: list[Borne] = []
    reader = csv.DictReader(io.StringIO(texte))
    for row in reader:
        coord = _parse_coord(row)
        if coord is None:
            continue
        puiss = row.get("puissance_nominale") or row.get("puissance")
        try:
            pkw = float(str(puiss).replace(",", ".")) if puiss else None
        except ValueError:
            pkw = None
        # Certaines sources expriment la puissance en W (ex. 22000) → kW.
        if pkw is not None and pkw > 1000:
            pkw = pkw / 1000.0
        bornes.append(
            Borne(lat=coord[0], lon=coord[1], puissance_kw=pkw,
                  operateur=row.get("nom_operateur") or row.get("operateur"))
        )
    return bornes


class ClientIRVE:
    """Accès aux bornes IRVE (réseau réel, ou lignes injectées en test)."""

    def __init__(self, bornes: list[Borne] | None = None, url: str | None = None):
        self._bornes = bornes
        self._url = url or os.environ.get("IRVE_DATASET_URL", IRVE_URL_DEFAUT)

    def _charger(self) -> list[Borne]:
        if self._bornes is not None:
            return self._bornes
        if self._url in _cache:
            return _cache[self._url]
        try:
            import requests

            resp = requests.get(self._url, timeout=30)
            resp.raise_for_status()
            bornes = _parse_rows(resp.text)
            logger.info("IRVE : %d bornes chargées depuis %s", len(bornes), self._url)
        except Exception as exc:  # noqa: BLE001 — connecteur tolérant
            logger.warning("IRVE indisponible (%s) — comptage à 0", exc)
            bornes = []
        _cache[self._url] = bornes
        self._bornes = bornes
        return bornes

    def compter(self, lat: float, lon: float) -> ComptageBornes:
        """Compte les bornes par palier de distance autour d'un point."""
        res = ComptageBornes()
        types: list[str] = []
        for b in self._charger():
            # Pré-filtre grossier (~0.12°≈13 km) pour éviter le haversine sur tout le pays.
            if abs(b.lat - lat) > 0.12 or abs(b.lon - lon) > 0.18:
                continue
            d = _haversine_km(lat, lon, b.lat, b.lon)
            if d <= 10:
                res.rayon_10km += 1
                types.append(b.type_label())
            if d <= 1:
                res.voisinage_1km += 1
            if d <= 0.15:
                res.sur_site += 1
        # Types les plus représentés (dédupliqués, ordre stable).
        res.types = list(dict.fromkeys(types))[:4]
        return res


__all__ = ["Borne", "ClientIRVE", "ComptageBornes"]
