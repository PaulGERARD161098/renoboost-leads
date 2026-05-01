"""Client API Recherche d'entreprises (recherche-entreprises.api.gouv.fr).

API publique gratuite, sans authentification.
Documentation : https://recherche-entreprises.api.gouv.fr/

Limites :
- 7 requêtes/seconde par IP
- Réponse JSON paginée
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

from ..common.logger import get_logger
from ..common.rate_limiter import RateLimiter

logger = get_logger(__name__)

# Endpoint principal
RECHERCHE_URL = "https://recherche-entreprises.api.gouv.fr/search"


# ════════════════════════════════════════════════════════════════
# Exceptions
# ════════════════════════════════════════════════════════════════


class RechercheEntreprisesError(Exception):
    """Erreur générique."""


class RechercheEntreprisesTransientError(RechercheEntreprisesError):
    """Erreur réseau/5xx — retryable."""


# ════════════════════════════════════════════════════════════════
# Config
# ════════════════════════════════════════════════════════════════


@dataclass
class RechercheClientConfig:
    rate_limiter: RateLimiter
    timeout_seconds: float = 12.0
    user_agent: str = "RenoboostLeadsBot/0.1 (+contact@renoboost.fr)"


# ════════════════════════════════════════════════════════════════
# Client
# ════════════════════════════════════════════════════════════════


class RechercheEntreprisesClient:
    """Wrapper de l'API recherche-entreprises.api.gouv.fr."""

    def __init__(self, config: RechercheClientConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.user_agent})

    @retry(
        retry=retry_if_exception_type(
            (RechercheEntreprisesTransientError, requests.RequestException)
        ),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def rechercher(
        self,
        query: str,
        code_postal: str | None = None,
        per_page: int = 10,
    ) -> list[dict[str, Any]]:
        """Recherche des entreprises par requête textuelle (nom + ville/CP idéalement).

        Args:
            query: ex "Hôtel Le Sud Montpellier"
            code_postal: filtre additionnel (ex: "34000") — réduit le bruit
            per_page: nb résultats (max 25)

        Returns:
            Liste des résultats bruts (peut être vide).
        """
        if not query or not query.strip():
            return []

        params: dict[str, Any] = {
            "q": query.strip(),
            "per_page": min(per_page, 25),
        }
        if code_postal:
            params["code_postal"] = code_postal

        # Politesse
        self.config.rate_limiter.acquire()

        logger.debug("Recherche entreprises: %s (cp=%s)", query, code_postal)

        try:
            resp = self.session.get(
                RECHERCHE_URL,
                params=params,
                timeout=self.config.timeout_seconds,
            )
        except requests.RequestException as e:
            raise RechercheEntreprisesTransientError(f"Erreur réseau: {e}") from e

        if 500 <= resp.status_code < 600:
            raise RechercheEntreprisesTransientError(f"HTTP {resp.status_code}")

        if resp.status_code == 429:
            # Rate limit côté serveur — on relance après pause
            raise RechercheEntreprisesTransientError("HTTP 429 rate-limited")

        if resp.status_code != 200:
            logger.warning("HTTP %s pour query=%r", resp.status_code, query)
            return []

        try:
            data = resp.json()
        except ValueError:
            logger.warning("Réponse non-JSON pour query=%r", query)
            return []

        return data.get("results", []) or []

    def health_check(self) -> tuple[bool, str]:
        """Test rapide de connectivité (gratuit)."""
        try:
            results = self.rechercher("test", per_page=1)
            return True, f"OK ({len(results)} résultats sur 'test')"
        except RechercheEntreprisesError as e:
            return False, str(e)
        except Exception as e:  # noqa: BLE001
            return False, f"Erreur inattendue: {type(e).__name__}: {e}"
