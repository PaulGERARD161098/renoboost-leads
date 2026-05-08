"""Client Google Places API (New) — wrapper REST.

Documentation officielle :
- Text Search : https://developers.google.com/maps/documentation/places/web-service/text-search
- Nearby Search : https://developers.google.com/maps/documentation/places/web-service/nearby-search
- Place Details : https://developers.google.com/maps/documentation/places/web-service/place-details

Particularités Places API (New) :
- Endpoints en POST (et non GET)
- Authentification via header `X-Goog-Api-Key`
- Field masks obligatoires via header `X-Goog-FieldMask` → réduit la facture
- Tarification "essentials/pro/enterprise" selon les champs demandés
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..common.budget_guard import BudgetGuard
from ..common.logger import get_logger
from ..common.rate_limiter import RateLimiter

logger = get_logger(__name__)

# ─── Endpoints ───
TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
NEARBY_SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"

# ─── Field masks ───
# On reste en niveau "Pro" autant que possible (champs essentiels + contact + rating)
# Tarification mai 2026 : Pro ~0.017€/req, Enterprise ~0.020€/req
FIELD_MASK_SEARCH = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.types",
    "places.primaryType",
    "places.businessStatus",
    "places.nationalPhoneNumber",
    "places.internationalPhoneNumber",
    "places.websiteUri",
    "places.rating",
    "places.userRatingCount",
    "places.priceLevel",
    "places.googleMapsUri",
])

# ─── Coûts estimés (€) — à recaler avec la facturation réelle après run ───
COUT_TEXT_SEARCH_EUR = 0.032
COUT_NEARBY_SEARCH_EUR = 0.032


# ════════════════════════════════════════════════════════════════
# Exceptions
# ════════════════════════════════════════════════════════════════


class PlacesAPIError(Exception):
    """Erreur générique de l'API Places."""


class PlacesAuthError(PlacesAPIError):
    """403 Forbidden / 401 Unauthorized."""


class PlacesQuotaError(PlacesAPIError):
    """429 Too Many Requests / quota dépassé."""


class PlacesTransientError(PlacesAPIError):
    """5xx / réseau — retryable."""


# ════════════════════════════════════════════════════════════════
# Modèle de configuration runtime
# ════════════════════════════════════════════════════════════════


@dataclass
class PlacesClientConfig:
    api_key: str
    rate_limiter: RateLimiter
    budget: BudgetGuard
    timeout_seconds: float = 15.0
    language_code: str = "fr"
    region_code: str = "FR"


# ════════════════════════════════════════════════════════════════
# Client
# ════════════════════════════════════════════════════════════════


class PlacesClient:
    """Wrapper Google Places API (New)."""

    def __init__(self, config: PlacesClientConfig):
        self.config = config
        self.session = requests.Session()

    # ─── Headers communs ───
    def _headers(self, field_mask: str) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.config.api_key,
            "X-Goog-FieldMask": field_mask,
            "Accept-Language": self.config.language_code,
        }

    # ─── Gestion des erreurs HTTP ───
    @staticmethod
    def _raise_for_status(resp: requests.Response) -> None:
        if resp.status_code == 200:
            return
        body_excerpt = resp.text[:500] if resp.text else ""
        if resp.status_code in (401, 403):
            raise PlacesAuthError(
                f"HTTP {resp.status_code} — vérifier la clé API et ses restrictions IP. "
                f"Corps: {body_excerpt}"
            )
        if resp.status_code == 429:
            raise PlacesQuotaError(f"HTTP 429 — quota dépassé. Corps: {body_excerpt}")
        if 500 <= resp.status_code < 600:
            raise PlacesTransientError(f"HTTP {resp.status_code} — erreur serveur. {body_excerpt}")
        raise PlacesAPIError(f"HTTP {resp.status_code} — {body_excerpt}")

    # ─── Text Search ───
    @retry(
        retry=retry_if_exception_type((PlacesTransientError, requests.RequestException)),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def text_search(
        self,
        query: str,
        latitude: float | None = None,
        longitude: float | None = None,
        rayon_metres: int | None = None,
        max_results: int = 20,
    ) -> dict[str, Any]:
        """Lance un Text Search.

        Si lat/lng/rayon fournis → bias géographique + restriction à un cercle.
        """
        payload: dict[str, Any] = {
            "textQuery": query,
            "languageCode": self.config.language_code,
            "regionCode": self.config.region_code,
            "pageSize": min(20, max_results),
        }

        if latitude is not None and longitude is not None and rayon_metres is not None:
            # Restriction stricte au cercle (pas juste un bias)
            payload["locationBias"] = {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": float(rayon_metres),
                }
            }

        # Rate limit + Budget
        self.config.rate_limiter.acquire()
        self.config.budget.ajouter_cout(COUT_TEXT_SEARCH_EUR, contexte=f"text_search:{query}")

        logger.debug("Text Search: query=%s pos=(%.3f,%.3f) r=%sm",
                     query, latitude or 0, longitude or 0, rayon_metres)

        try:
            resp = self.session.post(
                TEXT_SEARCH_URL,
                json=payload,
                headers=self._headers(FIELD_MASK_SEARCH),
                timeout=self.config.timeout_seconds,
            )
        except requests.RequestException as e:
            raise PlacesTransientError(f"Erreur réseau Text Search: {e}") from e

        self._raise_for_status(resp)
        return resp.json()

    # ─── Nearby Search ───
    @retry(
        retry=retry_if_exception_type((PlacesTransientError, requests.RequestException)),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def nearby_search(
        self,
        latitude: float,
        longitude: float,
        rayon_metres: int,
        included_types: list[str] | None = None,
        max_results: int = 20,
    ) -> dict[str, Any]:
        """Nearby Search — par type officiel Places.

        Plus efficace que Text Search quand le type Places est connu et précis.
        """
        payload: dict[str, Any] = {
            "languageCode": self.config.language_code,
            "regionCode": self.config.region_code,
            "maxResultCount": min(20, max_results),
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": float(rayon_metres),
                }
            },
        }
        if included_types:
            payload["includedTypes"] = included_types

        self.config.rate_limiter.acquire()
        self.config.budget.ajouter_cout(
            COUT_NEARBY_SEARCH_EUR, contexte=f"nearby:{included_types}"
        )

        logger.debug(
            "Nearby Search: types=%s pos=(%.3f,%.3f) r=%sm",
            included_types, latitude, longitude, rayon_metres,
        )

        try:
            resp = self.session.post(
                NEARBY_SEARCH_URL,
                json=payload,
                headers=self._headers(FIELD_MASK_SEARCH),
                timeout=self.config.timeout_seconds,
            )
        except requests.RequestException as e:
            raise PlacesTransientError(f"Erreur réseau Nearby Search: {e}") from e

        self._raise_for_status(resp)
        return resp.json()

    # ─── Health check ───
    def health_check(self) -> tuple[bool, str]:
        """Petit appel test pour valider la clé. Coûte ~0.032€."""
        try:
            # Recherche neutre
            self.text_search(query="restaurant Paris", max_results=1)
            return True, "OK"
        except PlacesAuthError as e:
            return False, f"Clé invalide ou IP non autorisée : {e}"
        except PlacesAPIError as e:
            return False, str(e)
        except Exception as e:  # noqa: BLE001
            return False, f"Erreur inattendue: {type(e).__name__}: {e}"
