"""Géocodeur Base Adresse Nationale (BAN).

Convertit une adresse en clair (ex « Allée de l'Ecopark, Wambrechies ») en
coordonnées (latitude, longitude), pour alimenter le mode `zone: point` de la
découverte SIRENE-first géographique (étage 0, endpoint near_point).

API publique gratuite, sans authentification :
https://api-adresse.data.gouv.fr/search

⚠ Prérequis réseau : `api-adresse.data.gouv.fr` doit figurer dans l'allowlist
de l'environnement (sinon HTTP 403 « Host not in allowlist »).
"""

from __future__ import annotations

from dataclasses import dataclass

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..common.logger import get_logger
from ..common.rate_limiter import RateLimiter

logger = get_logger(__name__)

BAN_URL = "https://api-adresse.data.gouv.fr/search/"

# En-deçà de ce score BAN, on considère le géocodage trop incertain pour
# centrer une recherche dessus (adresse mal orthographiée, lieu introuvable).
SCORE_MIN_DEFAUT = 0.4


# ════════════════════════════════════════════════════════════════
# Exceptions
# ════════════════════════════════════════════════════════════════


class GeocodageError(Exception):
    """Erreur générique de géocodage."""


class GeocodageTransientError(GeocodageError):
    """Erreur réseau/5xx — retryable."""


class AdresseIntrouvableError(GeocodageError):
    """Aucun résultat, ou score sous le seuil de confiance."""


# ════════════════════════════════════════════════════════════════
# Résultat
# ════════════════════════════════════════════════════════════════


@dataclass
class ResultatGeocodage:
    latitude: float
    longitude: float
    label: str  # libellé normalisé renvoyé par la BAN
    score: float


# ════════════════════════════════════════════════════════════════
# Client
# ════════════════════════════════════════════════════════════════


@dataclass
class GeocoderConfig:
    rate_limiter: RateLimiter
    timeout_seconds: float = 12.0
    user_agent: str = "RenoboostLeadsBot/0.1 (+contact@renoboost.fr)"
    score_min: float = SCORE_MIN_DEFAUT


class BANGeocoder:
    """Wrapper de l'API de géocodage Base Adresse Nationale."""

    def __init__(self, config: GeocoderConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.user_agent})

    @retry(
        retry=retry_if_exception_type(
            (GeocodageTransientError, requests.RequestException)
        ),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _appeler(self, adresse: str) -> dict:
        """Appel BAN brut. Lève GeocodageTransientError sur 5xx/429 (retry)."""
        self.config.rate_limiter.acquire()
        try:
            resp = self.session.get(
                BAN_URL,
                params={"q": adresse, "limit": 1},
                timeout=self.config.timeout_seconds,
            )
        except requests.RequestException as e:
            raise GeocodageTransientError(f"Erreur réseau: {e}") from e

        if 500 <= resp.status_code < 600:
            raise GeocodageTransientError(f"HTTP {resp.status_code}")
        if resp.status_code == 429:
            raise GeocodageTransientError("HTTP 429 rate-limited")
        if resp.status_code == 403:
            # Cas typique : host absent de l'allowlist réseau de l'environnement.
            raise GeocodageError(
                "HTTP 403 de la BAN — api-adresse.data.gouv.fr probablement "
                "absent de l'allowlist réseau de l'environnement."
            )
        if resp.status_code != 200:
            raise GeocodageError(f"HTTP {resp.status_code} de la BAN")

        try:
            return resp.json()
        except ValueError as e:
            raise GeocodageError(f"Réponse BAN non-JSON: {e}") from e

    def geocoder(self, adresse: str) -> ResultatGeocodage:
        """Géocode une adresse en clair en coordonnées.

        Args:
            adresse: ex « Allée de l'Ecopark, Wambrechies ».

        Returns:
            ResultatGeocodage (latitude, longitude, label, score).

        Raises:
            AdresseIntrouvableError: aucun résultat ou score < score_min.
            GeocodageError: erreur API non récupérable.
        """
        if not adresse or not adresse.strip():
            raise AdresseIntrouvableError("Adresse vide.")

        data = self._appeler(adresse.strip())
        features = data.get("features") or []
        if not features:
            raise AdresseIntrouvableError(f"Aucun résultat BAN pour : {adresse!r}")

        f = features[0]
        props = f.get("properties") or {}
        coords = (f.get("geometry") or {}).get("coordinates") or []
        if len(coords) < 2:
            raise AdresseIntrouvableError(
                f"Résultat BAN sans coordonnées pour : {adresse!r}"
            )

        # GeoJSON : coordinates = [longitude, latitude]
        longitude, latitude = float(coords[0]), float(coords[1])
        score = float(props.get("score") or 0.0)
        label = props.get("label") or adresse

        if score < self.config.score_min:
            raise AdresseIntrouvableError(
                f"Score BAN trop bas ({score:.2f} < {self.config.score_min}) "
                f"pour {adresse!r} → résolu en {label!r}. Précise l'adresse."
            )

        logger.info(
            "Géocodage BAN : %r → %r (lat=%s, lon=%s, score=%.2f)",
            adresse, label, latitude, longitude, score,
        )
        return ResultatGeocodage(
            latitude=latitude, longitude=longitude, label=label, score=score
        )
