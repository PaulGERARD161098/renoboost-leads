"""Porte a — connecteur géospatial OSM (Overpass) → CSV d'inventaire parkings.

Phase B de la roadmap APER : au lieu de fournir manuellement un CSV de parkings,
on interroge **OpenStreetMap via l'API Overpass** pour récupérer les parcs de
stationnement extérieurs d'une zone (bbox), calculer leur **surface réelle** à
partir de la géométrie, et écrire un CSV directement consommable par `aper run`.

- Client défensif (injection `http_post`, retry tenacity, dry-run sans réseau).
- Surface calculée par projection équirectangulaire locale + shoelace (précision
  suffisante pour des polygones de parking de quelques milliers de m²).
- Pré-filtre optionnel par surface (défaut = seuil légal APER 1 500 m²).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..common.logger import get_logger
from ..common.rate_limiter import RateLimiter
from .models import SEUIL_APER_M2, AperConfig, LigneParking

logger = get_logger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
RAYON_TERRE_M = 6_371_000.0


class OverpassError(RuntimeError):
    """Erreur d'appel Overpass (réseau, 4xx/5xx, parsing)."""


@dataclass
class Bbox:
    """Boîte englobante géographique (degrés)."""

    sud: float
    ouest: float
    nord: float
    est: float

    @classmethod
    def depuis_str(cls, s: str) -> Bbox:
        """Parse 'sud,ouest,nord,est' (ex. '50.60,2.90,50.70,3.10')."""
        try:
            sud, ouest, nord, est = (float(x) for x in s.split(","))
        except ValueError as e:
            raise ValueError(
                "bbox attendu : 'sud,ouest,nord,est' (4 nombres séparés par des virgules)"
            ) from e
        return cls(sud=sud, ouest=ouest, nord=nord, est=est)

    def as_overpass(self) -> str:
        return f"{self.sud},{self.ouest},{self.nord},{self.est}"


def surface_polygone_m2(points: list[tuple[float, float]]) -> float:
    """Surface (m²) d'un polygone lat/lon par projection équirectangulaire + shoelace.

    `points` : liste de (lat, lon) en degrés. L'anneau est refermé automatiquement.
    """
    if len(points) < 3:
        return 0.0
    lat_moy = math.radians(sum(p[0] for p in points) / len(points))
    cos_lat = math.cos(lat_moy)

    def projeter(lat: float, lon: float) -> tuple[float, float]:
        x = math.radians(lon) * cos_lat * RAYON_TERRE_M
        y = math.radians(lat) * RAYON_TERRE_M
        return x, y

    xy = [projeter(lat, lon) for lat, lon in points]
    aire2 = 0.0
    n = len(xy)
    for i in range(n):
        x1, y1 = xy[i]
        x2, y2 = xy[(i + 1) % n]
        aire2 += x1 * y2 - x2 * y1
    return abs(aire2) / 2.0


@dataclass
class OverpassConfig:
    base_url: str = OVERPASS_URL
    timeout_s: float = 90.0
    rate_limiter: RateLimiter | None = None
    http_post: Callable[..., requests.Response] | None = None
    user_agent: str = "RenoboostLeadsBot/0.1 (+contact@renoboost.fr)"


class OverpassClient:
    """Client Overpass — récupère les parkings (ways) d'une bbox avec géométrie."""

    def __init__(self, config: OverpassConfig | None = None):
        self.config = config or OverpassConfig()
        self._post = self.config.http_post or requests.post

    def _requete_ql(self, bbox: Bbox) -> str:
        b = bbox.as_overpass()
        # Parkings de surface (extérieurs) avec géométrie complète.
        return (
            "[out:json][timeout:60];"
            f'(way["amenity"="parking"]({b}););'
            "out geom;"
        )

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def chercher_parkings(self, bbox: Bbox) -> list[dict[str, Any]]:
        """Retourne les éléments OSM bruts (ways parking) de la bbox."""
        if self.config.rate_limiter:
            self.config.rate_limiter.acquire()
        resp = self._post(
            self.config.base_url,
            data={"data": self._requete_ql(bbox)},
            headers={"User-Agent": self.config.user_agent},
            timeout=self.config.timeout_s,
        )
        if resp.status_code >= 400:
            raise OverpassError(f"Overpass HTTP {resp.status_code} : {resp.text[:200]}")
        try:
            data = resp.json()
        except ValueError as e:
            raise OverpassError(f"Réponse non-JSON : {e}") from e
        elements = data.get("elements", [])
        return [e for e in elements if e.get("type") == "way"]

    def health_check(self) -> tuple[bool, str]:
        try:
            self.chercher_parkings(Bbox(48.85, 2.34, 48.86, 2.35))
            return True, "OK"
        except Exception as e:  # noqa: BLE001
            return False, str(e)


class OverpassClientDryRun(OverpassClient):
    """Client simulé : renvoie deux parkings synthétiques, aucun appel réseau."""

    def chercher_parkings(self, bbox: Bbox) -> list[dict[str, Any]]:  # noqa: ARG002
        return [
            {
                "type": "way",
                "id": 1001,
                "tags": {
                    "amenity": "parking",
                    "name": "Parking Carrefour Lens",
                    "operator": "Carrefour",
                    "addr:postcode": "62300",
                    "addr:city": "Lens",
                },
                # ~ 0.0012° x 0.0012° ≈ 130m x 130m ≈ 17 000 m²
                "geometry": [
                    {"lat": 50.4300, "lon": 2.8300},
                    {"lat": 50.4300, "lon": 2.8312},
                    {"lat": 50.4312, "lon": 2.8312},
                    {"lat": 50.4312, "lon": 2.8300},
                ],
            },
            {
                "type": "way",
                "id": 1002,
                "tags": {
                    "amenity": "parking",
                    "name": "Parking Lidl Béthune",
                    "addr:postcode": "62400",
                },
                # ~ petit parking ≈ 1 200 m² (sous le seuil APER, sera filtré)
                "geometry": [
                    {"lat": 50.5300, "lon": 2.6400},
                    {"lat": 50.5300, "lon": 2.6403},
                    {"lat": 50.5303, "lon": 2.6403},
                    {"lat": 50.5303, "lon": 2.6400},
                ],
            },
        ]


def element_osm_vers_ligne(el: dict[str, Any]) -> LigneParking | None:
    """Convertit un way OSM (avec `geometry`) en LigneParking, ou None si invalide."""
    geom = el.get("geometry") or []
    points = [(g["lat"], g["lon"]) for g in geom if "lat" in g and "lon" in g]
    if len(points) < 3:
        return None
    surface = surface_polygone_m2(points)
    if surface <= 0:
        return None
    tags = el.get("tags") or {}
    nom = tags.get("name") or tags.get("brand") or tags.get("operator")
    lat_c = sum(p[0] for p in points) / len(points)
    lon_c = sum(p[1] for p in points) / len(points)
    return LigneParking(
        surface_m2=round(surface, 1),
        identifiant=f"osm:way/{el.get('id')}",
        nom=nom,
        raison_sociale=tags.get("operator") or tags.get("brand"),
        code_postal=tags.get("addr:postcode"),
        commune=tags.get("addr:city"),
        latitude=round(lat_c, 6),
        longitude=round(lon_c, 6),
        source="aper_osm",
    )


def recuperer_parkings(
    bbox: Bbox,
    *,
    client: OverpassClient | None = None,
    surface_min_m2: float = SEUIL_APER_M2,
) -> list[LigneParking]:
    """Récupère les parkings OSM d'une bbox, convertit, pré-filtre par surface."""
    client = client or OverpassClient()
    elements = client.chercher_parkings(bbox)
    lignes: list[LigneParking] = []
    for el in elements:
        ligne = element_osm_vers_ligne(el)
        if ligne is not None and ligne.surface_m2 >= surface_min_m2:
            lignes.append(ligne)
    logger.info(
        "Overpass : %d ways → %d parkings ≥ %.0f m²",
        len(elements), len(lignes), surface_min_m2,
    )
    return lignes


def ecrire_inventaire_csv(
    lignes: list[LigneParking],
    output_path: Path,
    config: AperConfig | None = None,
) -> Path:
    """Écrit un CSV d'inventaire au format attendu par `aper run` (lire_csv_parkings)."""
    import csv

    config = config or AperConfig()
    # mapping_colonnes : {COLONNE_FICHIER: champ_modele}.
    colonnes = list(config.mapping_colonnes.keys())

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding=config.encodage, newline="") as fh:
        writer = csv.writer(fh, delimiter=config.separateur)
        writer.writerow(colonnes)
        for ligne in lignes:
            row = []
            for col in colonnes:
                champ = config.mapping_colonnes[col]
                val = getattr(ligne, champ, None)
                row.append("" if val is None else val)
            writer.writerow(row)
    return output_path
