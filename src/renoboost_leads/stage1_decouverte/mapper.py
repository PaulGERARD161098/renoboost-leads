"""Mapping : réponse brute Places API (New) → `LeadStage1` Pydantic.

L'API renvoie des structures imbriquées variables. Ce module isole la logique
de mapping pour la rendre testable et facile à mettre à jour si Google modifie
le format.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from ..models import LeadStage1


def _safe_get(d: dict[str, Any] | None, *keys: str, default: Any = None) -> Any:
    """Accès profond sécurisé à un dict imbriqué."""
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


# Régex pour extraire CP + ville d'une adresse française "12 av. Foch, 34000 Montpellier, France"
_RE_CP_VILLE = re.compile(r"\b(\d{5})\b\s+([^,]+?)(?:,|$)")


def _extract_cp_ville(adresse: str | None) -> tuple[str | None, str | None]:
    if not adresse:
        return None, None
    m = _RE_CP_VILLE.search(adresse)
    if not m:
        return None, None
    return m.group(1).strip(), m.group(2).strip()


# Niveaux de prix Places (New) — cf. https://developers.google.com/maps/documentation/places/web-service/data-fields
_PRICE_LEVEL_MAP = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}


def place_to_lead(
    place: dict[str, Any],
    secteur_recherche: str = "",
    requete_origine: str = "",
) -> LeadStage1 | None:
    """Convertit une fiche Place brute en LeadStage1.

    Renvoie None si la fiche est manifestement inexploitable (pas de place_id ou pas de nom).
    """
    place_id = place.get("id")
    if not place_id:
        return None

    nom = _safe_get(place, "displayName", "text") or ""
    if not nom:
        return None

    adresse_complete = place.get("formattedAddress")
    code_postal, ville = _extract_cp_ville(adresse_complete)

    latitude = _safe_get(place, "location", "latitude")
    longitude = _safe_get(place, "location", "longitude")

    types = place.get("types") or []
    primary_type = place.get("primaryType")

    price_level_raw = place.get("priceLevel")
    niveau_prix = _PRICE_LEVEL_MAP.get(price_level_raw) if price_level_raw else None

    return LeadStage1(
        place_id=place_id,
        extraction_date=datetime.now(timezone.utc),
        nom=nom.strip(),
        adresse=adresse_complete,
        ville=ville,
        code_postal=code_postal,
        pays="France",
        latitude=float(latitude) if latitude is not None else None,
        longitude=float(longitude) if longitude is not None else None,
        telephone=place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber"),
        site_web=place.get("websiteUri"),
        note=place.get("rating"),
        nb_avis=place.get("userRatingCount"),
        type_principal=primary_type,
        types=list(types),
        statut_business=place.get("businessStatus"),
        niveau_prix=niveau_prix,
        google_maps_url=place.get("googleMapsUri"),
        secteur_recherche=secteur_recherche,
        requete_origine=requete_origine,
    )
