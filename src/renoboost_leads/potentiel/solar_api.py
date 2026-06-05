"""Booster optionnel : Google Solar API (buildingInsights) pour le potentiel solaire.

Quand une clé est disponible ET que le bâtiment est couvert (France : partielle),
l'API renvoie la surface de toiture et la surface réellement équipable en panneaux
(`maxArrayAreaMeters2`) — bien plus précis que l'estimation Vision. Sinon on retombe
proprement sur l'emprise bâtie IGN + Vision.

Tolérant : pas de clé / hors couverture / erreur → None.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from ..common.logger import get_logger

logger = get_logger(__name__)

_ENDPOINT = "https://solar.googleapis.com/v1/buildingInsights:findClosest"


def cle_solar_api() -> str | None:
    """Clé Google Solar API (dédiée, sinon la clé Google Places si Solar activée)."""
    return (
        os.environ.get("GOOGLE_SOLAR_API_KEY")
        or os.environ.get("GOOGLE_PLACES_API_KEY")
        or None
    )


def _fetch(lat: float, lon: float, api_key: str, timeout: float) -> dict[str, Any]:
    import requests

    resp = requests.get(
        _ENDPOINT,
        params={
            "location.latitude": lat,
            "location.longitude": lon,
            "requiredQuality": "LOW",
            "key": api_key,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def surfaces_solar_api(
    lat: float,
    lon: float,
    *,
    api_key: str | None = None,
    timeout: float = 15.0,
    fetch: Callable[[float, float, str, float], dict[str, Any]] | None = None,
) -> tuple[float, float] | None:
    """(surface_toiture_m2, surface_exploitable_m2) via Google Solar API, ou None.

    `fetch` est injectable pour les tests.
    """
    key = api_key or cle_solar_api()
    if not key:
        return None
    try:
        data = (fetch or _fetch)(lat, lon, key, timeout)
        sp = data.get("solarPotential") or {}
        toiture = (sp.get("wholeRoofStats") or {}).get("areaMeters2")
        exploitable = sp.get("maxArrayAreaMeters2")
        toiture = float(toiture) if toiture is not None else None
        exploitable = float(exploitable) if exploitable is not None else None
        if exploitable is None and toiture is None:
            return None
        # Si une seule des deux valeurs est connue, on complète raisonnablement.
        if toiture is None:
            toiture = exploitable
        if exploitable is None:
            exploitable = toiture
        return round(toiture, 1), round(exploitable, 1)
    except Exception as exc:  # noqa: BLE001 — booster optionnel, jamais bloquant
        logger.info("Google Solar API indisponible (%s) — repli IGN/Vision", exc)
        return None


__all__ = ["cle_solar_api", "surfaces_solar_api"]
