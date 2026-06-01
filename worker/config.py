"""Configuration du worker, lue depuis l'environnement."""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    """Variable d'environnement requise manquante."""


@dataclass(frozen=True)
class WorkerConfig:
    supabase_url: str
    service_role_key: str
    poll_interval_s: float = 5.0
    mode: str = "demo"  # "demo" | "real"
    max_leads: int = 500
    max_budget_eur: float = 50.0
    request_timeout_s: float = 30.0

    @property
    def rest_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/rest/v1"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> WorkerConfig:
        env = env if env is not None else dict(os.environ)

        url = env.get("SUPABASE_URL", "").strip()
        key = env.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        missing = [
            name
            for name, val in (("SUPABASE_URL", url), ("SUPABASE_SERVICE_ROLE_KEY", key))
            if not val
        ]
        if missing:
            raise ConfigError(
                "Variables manquantes : " + ", ".join(missing) + ". "
                "Définis-les dans l'environnement Railway (clé service_role, pas anon)."
            )

        mode = env.get("WORKER_MODE", "demo").strip().lower()
        if mode not in ("demo", "real"):
            raise ConfigError(f"WORKER_MODE invalide : {mode!r} (attendu 'demo' ou 'real').")

        return cls(
            supabase_url=url,
            service_role_key=key,
            poll_interval_s=float(env.get("WORKER_POLL_INTERVAL_S", "5")),
            mode=mode,
            max_leads=int(env.get("MAX_LEADS_PER_RUN", "500")),
            max_budget_eur=float(env.get("MAX_BUDGET_EUR_PER_RUN", "50")),
            request_timeout_s=float(env.get("WORKER_REQUEST_TIMEOUT_S", "30")),
        )
