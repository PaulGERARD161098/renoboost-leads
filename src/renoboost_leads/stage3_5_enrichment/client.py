"""Wrapper API Dropcontact pour l'enrichissement L3.5.

Dropcontact fonctionne en deux temps :
1. POST /batch avec une liste de leads → renvoie un `request_id`
2. GET /batch/<request_id> en polling jusqu'à `success=True`

Conçu pour être facilement mockable dans les tests : on injecte une fonction
`http_post` / `http_get` (par défaut wrap autour de `requests`).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..common.budget_guard import BudgetExceededError, BudgetGuard
from ..common.logger import get_logger
from ..common.rate_limiter import RateLimiter

logger = get_logger(__name__)


DROPCONTACT_BASE_URL = "https://api.dropcontact.com"


class DropcontactError(RuntimeError):
    """Erreur générique d'appel Dropcontact (réseau, 4xx, 5xx, parsing)."""


class DropcontactTimeoutError(DropcontactError):
    """Le polling a dépassé `poll_timeout_s` sans réponse `success=True`."""


@dataclass
class DropcontactReponse:
    """Réponse brute Dropcontact pour un lot, indexée par position d'entrée.

    `data` contient la liste retournée par Dropcontact dans le même ordre que
    le batch envoyé. Chaque élément est un dict tel que renvoyé par l'API.
    """

    request_id: str
    data: list[dict[str, Any]]
    cout_eur: float


@dataclass
class DropcontactClientConfig:
    api_key: str
    base_url: str = DROPCONTACT_BASE_URL
    language: str = "fr"
    siren: bool = True
    poll_initial_delay_s: float = 10.0
    poll_interval_s: float = 10.0
    poll_timeout_s: float = 600.0
    cout_par_lead_eur: float = 0.50
    rate_limiter: RateLimiter | None = None
    budget: BudgetGuard | None = None
    # Hooks injectables pour tests (mock complet sans monkeypatch global)
    http_post: Callable[..., requests.Response] | None = None
    http_get: Callable[..., requests.Response] | None = None
    sleep_fn: Callable[[float], None] = field(default=time.sleep)


class DropcontactClient:
    """Façade Dropcontact — POST batch + polling jusqu'à résultat."""

    def __init__(self, config: DropcontactClientConfig):
        self.config = config
        self._post = config.http_post or requests.post
        self._get = config.http_get or requests.get
        self._sleep = config.sleep_fn

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Access-Token": self.config.api_key,
        }

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _post_batch(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.config.rate_limiter:
            self.config.rate_limiter.acquire()
        url = f"{self.config.base_url}/batch"
        resp = self._post(url, json=payload, headers=self._headers(), timeout=30)
        if resp.status_code >= 400:
            raise DropcontactError(
                f"POST /batch HTTP {resp.status_code} : {resp.text[:200]}"
            )
        try:
            return resp.json()
        except ValueError as e:
            raise DropcontactError(f"Réponse POST non-JSON : {e}") from e

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _get_batch(self, request_id: str) -> dict[str, Any]:
        url = f"{self.config.base_url}/batch/{request_id}"
        resp = self._get(url, headers=self._headers(), timeout=30)
        if resp.status_code >= 400:
            raise DropcontactError(
                f"GET /batch/{request_id} HTTP {resp.status_code} : {resp.text[:200]}"
            )
        try:
            return resp.json()
        except ValueError as e:
            raise DropcontactError(f"Réponse GET non-JSON : {e}") from e

    def enrichir_batch(self, lots: list[dict[str, Any]]) -> DropcontactReponse:
        """Envoie un lot de leads à Dropcontact et attend le résultat.

        `lots` est une liste de payloads par lead, ex:
            [{"first_name": "Paul", "last_name": "Durand",
              "company": "Acme", "siren": "12345...",
              "website": "acme.fr"}, ...]

        Retourne un `DropcontactReponse` avec la liste résultats dans le même
        ordre que `lots`. Le coût est estimé = `len(lots) * cout_par_lead_eur`.

        Lève :
        - `DropcontactError` en cas d'erreur HTTP / réponse invalide
        - `DropcontactTimeoutError` si le polling dépasse `poll_timeout_s`
        - `BudgetExceededError` si le budget guard refuse l'appel
        """
        if not lots:
            return DropcontactReponse(request_id="", data=[], cout_eur=0.0)

        cout = len(lots) * self.config.cout_par_lead_eur
        if self.config.budget:
            self.config.budget.ajouter_cout(cout, contexte=f"L3.5 Dropcontact ({len(lots)} leads)")

        payload = {
            "data": lots,
            "siren": self.config.siren,
            "language": self.config.language,
        }

        post_response = self._post_batch(payload)
        request_id = post_response.get("request_id")
        if not request_id:
            raise DropcontactError(
                f"Pas de request_id dans la réponse POST : {post_response}"
            )

        logger.info(
            "L3.5 Dropcontact : batch envoyé (%d leads, request_id=%s)",
            len(lots),
            request_id,
        )

        # Polling
        self._sleep(self.config.poll_initial_delay_s)
        elapsed = self.config.poll_initial_delay_s
        while elapsed <= self.config.poll_timeout_s:
            result = self._get_batch(request_id)
            if result.get("success") is True and "data" in result:
                logger.info(
                    "L3.5 Dropcontact : résultat reçu (request_id=%s, %d items, %.2fs)",
                    request_id,
                    len(result["data"]),
                    elapsed,
                )
                return DropcontactReponse(
                    request_id=request_id,
                    data=result["data"],
                    cout_eur=cout,
                )
            # Pas encore prêt — on continue
            self._sleep(self.config.poll_interval_s)
            elapsed += self.config.poll_interval_s

        raise DropcontactTimeoutError(
            f"Polling Dropcontact > {self.config.poll_timeout_s}s "
            f"sans success=True (request_id={request_id})"
        )


def lead_payload_dropcontact(
    *,
    first_name: str | None,
    last_name: str | None,
    company: str | None,
    website: str | None,
    siren: str | None,
    email: str | None = None,
) -> dict[str, Any]:
    """Construit le payload d'un lead pour Dropcontact (champs vides ignorés)."""
    payload: dict[str, Any] = {}
    if first_name:
        payload["first_name"] = first_name
    if last_name:
        payload["last_name"] = last_name
    if company:
        payload["company"] = company
    if website:
        payload["website"] = website
    if siren:
        payload["siren"] = siren
    if email:
        payload["email"] = email
    return payload


# Re-export pour l'API publique du module
__all__ = [
    "DropcontactClient",
    "DropcontactClientConfig",
    "DropcontactError",
    "DropcontactTimeoutError",
    "DropcontactReponse",
    "BudgetExceededError",
    "lead_payload_dropcontact",
]
