"""Wrapper HTTP autour de l'API Instantly v2.

Endpoints couverts (Phase B minimal) :
- `POST /campaigns` — créer une campagne
- `GET  /campaigns` — lister les campagnes
- `GET  /campaigns/{id}/analytics` — métriques (envoyés, ouverts, répondu)
- `POST /campaigns/{id}/leads` — ajouter des leads
- `POST /campaigns/{id}/pause` — mettre en pause

Mode dry-run : si aucune clé n'est configurée OU si `INSTANTLY_DRY_RUN=true`,
toutes les méthodes renvoient des payloads simulés sans hit réseau. Permet
de développer/tester sans abonnement actif.

L'API Instantly évolue ; les payloads sont volontairement permissifs côté
parsing (on ne valide pas les schémas en sortie, juste on remonte le JSON).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import requests

from ..settings import get_settings


class InstantlyError(RuntimeError):
    """Erreur API ou réseau côté Instantly."""


@dataclass
class InstantlyConfig:
    api_key: str | None
    base_url: str
    dry_run: bool

    @classmethod
    def from_settings(cls) -> InstantlyConfig:
        s = get_settings()
        key = (
            s.instantly_api_key.get_secret_value()
            if s.instantly_api_key is not None
            else None
        )
        return cls(
            api_key=key or None,
            base_url=s.instantly_base_url.rstrip("/"),
            dry_run=s.instantly_dry_run or not key,
        )


class InstantlyClient:
    """Client HTTP minimaliste. Dry-run renvoie des payloads simulés."""

    def __init__(
        self,
        config: InstantlyConfig | None = None,
        *,
        session: requests.Session | None = None,
        timeout_s: float = 20.0,
    ) -> None:
        self.config = config or InstantlyConfig.from_settings()
        self._session = session or requests.Session()
        self._timeout = timeout_s

    # ─── Helpers ─────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.config.api_key:
            h["Authorization"] = f"Bearer {self.config.api_key}"
        return h

    def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        url = f"{self.config.base_url}{path}"
        try:
            resp = self._session.request(
                method,
                url,
                headers=self._headers(),
                timeout=self._timeout,
                **kwargs,
            )
        except requests.RequestException as e:
            raise InstantlyError(f"Réseau : {e!s}") from e
        if resp.status_code >= 400:
            raise InstantlyError(
                f"HTTP {resp.status_code} sur {method} {path} : "
                f"{resp.text[:300]}"
            )
        try:
            return resp.json() if resp.content else {}
        except ValueError as e:
            raise InstantlyError(f"Réponse non-JSON sur {path}") from e

    # ─── Public API ──────────────────────────────────────────────────

    def is_dry_run(self) -> bool:
        return self.config.dry_run

    def create_campaign(
        self,
        name: str,
        *,
        from_email: str | None = None,
        sequence_steps: list[dict] | None = None,
    ) -> dict:
        """Crée une campagne. En dry-run renvoie un id simulé."""
        if self.config.dry_run:
            return {
                "id": f"dry-{uuid.uuid4().hex[:8]}",
                "name": name,
                "from_email": from_email,
                "status": "draft",
                "sequence_steps": sequence_steps or [],
                "dry_run": True,
            }
        body = {"name": name}
        if from_email:
            body["from_email"] = from_email
        if sequence_steps:
            body["sequence_steps"] = sequence_steps
        return self._request("POST", "/campaigns", json=body)

    def list_campaigns(self, limit: int = 50) -> list[dict]:
        if self.config.dry_run:
            return []
        data = self._request("GET", f"/campaigns?limit={int(limit)}")
        items = data.get("items") or data.get("campaigns") or []
        return items if isinstance(items, list) else []

    def add_leads(self, campaign_id: str, leads: list[dict]) -> dict:
        """Ajoute des leads (chaque lead = dict avec au moins email)."""
        if not leads:
            return {"added": 0, "skipped": 0}
        if self.config.dry_run:
            return {
                "campaign_id": campaign_id,
                "added": len(leads),
                "skipped": 0,
                "dry_run": True,
            }
        return self._request(
            "POST", f"/campaigns/{campaign_id}/leads", json={"leads": leads}
        )

    def get_campaign_metrics(self, campaign_id: str) -> dict:
        """Renvoie métriques (envoyés, ouverts, clics, répondus)."""
        if self.config.dry_run:
            return {
                "campaign_id": campaign_id,
                "sent": 0,
                "opened": 0,
                "clicked": 0,
                "replied": 0,
                "bounced": 0,
                "dry_run": True,
            }
        return self._request("GET", f"/campaigns/{campaign_id}/analytics")

    def pause_campaign(self, campaign_id: str) -> dict:
        if self.config.dry_run:
            return {
                "campaign_id": campaign_id,
                "status": "paused",
                "dry_run": True,
            }
        return self._request("POST", f"/campaigns/{campaign_id}/pause")
