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
    "pour évaluer son potentiel solaire (panneaux en toiture et ombrières de parking).\n"
    "Réponds UNIQUEMENT par un objet JSON valide, sans texte autour, au format :\n"
    '{"score":<0-100>,"verdict":"<phrase courte>","toiture":{"presente":<bool>,'
    '"type":"plate|inclinee|inconnue","surface_estimee_m2":<number|null>},'
    '"parking":{"present":<bool>,"surface_estimee_m2":<number|null>,'
    '"ombrieres_possibles":<bool>},"commentaire":"<2-3 phrases>"}\n'
    "Le score reflète l'intérêt global (grandes surfaces planes = élevé). "
    "Sois prudent si l'image est ambiguë."
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


def analyser_potentiel(
    lat: float, lon: float, api_key: str, timeout: float = 30.0
) -> dict[str, Any] | None:
    """Retourne le dict d'analyse (ou None si indisponible/erreur)."""
    try:
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
        if parsed is None:
            return None
        parsed["image_url"] = url
        parsed["analyse_le"] = datetime.now(timezone.utc).isoformat()
        return parsed
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
