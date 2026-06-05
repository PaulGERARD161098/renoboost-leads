"""Analyse 'potentiel solaire' d'un lead via vue aérienne IGN + Claude Vision.

Utilisé par le worker en mode réel quand WORKER_SATELLITE est activé. Volontairement
tolérant : toute erreur renvoie None (l'enrichissement est optionnel, jamais bloquant).
"""

from __future__ import annotations

import base64
import json
import logging
import math
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import requests

log = logging.getLogger("renoboost.worker.satellite")

_WMS = "https://data.geopf.fr/wms-r/wms"
_R = 6378137.0
_DEMI_COTE_M = 130.0
_MODEL = os.environ.get("WORKER_SATELLITE_MODEL", "claude-haiku-4-5")

_PROMPT = (
    "Tu analyses une vue aérienne IGN (orthophoto) centrée sur le site d'une entreprise, "
    "pour Rossini Energy (solaire en toiture, ombrières de parking, bornes de recharge). "
    "Décris UNIQUEMENT ce que tu OBSERVES (n'invente rien, ne calcule pas de score).\n"
    "Réponds UNIQUEMENT par un objet JSON valide, sans texte autour, au format :\n"
    '{"toiture":{"presente":<bool>,'
    '"type":"plate|inclinee|inclinee_nord|encombree|inconnue",'
    '"surface_estimee_m2":<number|null>,"ratio_exploitable":<number 0-1|null>},'
    '"parking":{"present":<bool>,"surface_estimee_m2":<number|null>,'
    '"nb_places_estime":<integer|null>,"partage":<bool|null>},'
    '"bornes_visibles":<integer>}\n'
    "ratio_exploitable = part de toiture réellement équipable (hors édicules, "
    "lanterneaux, ombres). partage = parking partagé entre plusieurs enseignes/occupants. "
    "bornes_visibles = nombre de bornes de recharge VE visibles sur le site. "
    "Mets null si tu n'es pas sûr d'une valeur chiffrée."
)


def _ign_url(lat: float, lon: float) -> str:
    x = _R * math.radians(lon)
    y = _R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    bbox = f"{x - _DEMI_COTE_M},{y - _DEMI_COTE_M},{x + _DEMI_COTE_M},{y + _DEMI_COTE_M}"
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetMap",
        "LAYERS": "ORTHOIMAGERY.ORTHOPHOTOS",
        "STYLES": "",
        "CRS": "EPSG:3857",
        "BBOX": bbox,
        "WIDTH": "640",
        "HEIGHT": "640",
        "FORMAT": "image/jpeg",
    }
    return f"{_WMS}?{urlencode(params)}"


def _parse_json(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        debut = text.find("{")
        fin = text.rfind("}")
        if debut != -1 and fin > debut:
            try:
                return json.loads(text[debut : fin + 1])
            except Exception:  # noqa: BLE001
                return None
        return None


def _vision_observations(
    lat: float, lon: float, api_key: str, timeout: float
) -> tuple[dict[str, Any], str] | None:
    """Appelle Claude Vision sur l'orthophoto → (observations, image_url)."""
    url = _ign_url(lat, lon)
    img = requests.get(url, timeout=timeout)
    if img.status_code != 200 or len(img.content) < 1000:
        return None
    b64 = base64.b64encode(img.content).decode("ascii")
    res = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": _MODEL,
            "max_tokens": 700,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": _PROMPT},
                    ],
                }
            ],
        },
        timeout=timeout,
    )
    if res.status_code != 200:
        log.warning("Vision satellite HTTP %s", res.status_code)
        return None
    data = res.json()
    text = "".join(
        b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
    )
    parsed = _parse_json(text)
    return (parsed, url) if parsed is not None else None


def analyser_potentiel(
    lat: float,
    lon: float,
    api_key: str,
    timeout: float = 30.0,
    *,
    signaux_ve: bool = False,
    exploitant: str | None = None,
) -> dict[str, Any] | None:
    """Analyse les 3 potentiels (solaire/ombrières/bornes) → dict, ou None.

    Combine l'observation Claude Vision (orthophoto IGN), la surface d'emprise
    bâtie IGN et le comptage de bornes IRVE, puis applique le scoring /10.
    Tolérant : toute panne renvoie None et n'interrompt jamais le run.
    """
    from renoboost_leads.potentiel.analyse import analyser_potentiels
    from renoboost_leads.potentiel.ign import surface_batie_m2
    from renoboost_leads.potentiel.irve import ClientIRVE
    from renoboost_leads.potentiel.solar_api import surfaces_solar_api

    try:
        obs = _vision_observations(lat, lon, api_key, timeout)
        if obs is None:
            return None
        vision, url = obs
        # Surface toiture : Google Solar API si dispo (précis), sinon emprise IGN.
        solar = surfaces_solar_api(lat, lon)
        if solar is not None:
            surface_toiture, surface_exploitable = solar
        else:
            surface_toiture, surface_exploitable = surface_batie_m2(lat, lon), None
        analyse = analyser_potentiels(
            latitude=lat,
            longitude=lon,
            vision=vision,
            signaux_ve=signaux_ve,
            irve=ClientIRVE(),
            surface_batie_m2=surface_toiture,
            surface_exploitable_m2=surface_exploitable,
            exploitant_probable=exploitant,
            image_url=url,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
        )
        return analyse.model_dump()
    except Exception:  # noqa: BLE001 — enrichissement optionnel, jamais bloquant
        log.exception("Analyse satellite échouée")
        return None


def satellite_active() -> bool:
    return os.environ.get("WORKER_SATELLITE", "").strip().lower() in ("1", "true", "yes")


def satellite_max() -> int:
    try:
        return int(os.environ.get("WORKER_SATELLITE_MAX", "60"))
    except ValueError:
        return 60
