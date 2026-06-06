"""Client PostgREST minimal pour Supabase (service_role).

On parle directement à `/rest/v1` en `requests` plutôt qu'au SDK `supabase-py`
pour garder le worker léger et sans dépendance lourde sur Railway.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupabaseRest:
    def __init__(self, rest_url: str, service_role_key: str, timeout_s: float = 30.0) -> None:
        self._rest_url = rest_url.rstrip("/")
        self._timeout = timeout_s
        self._session = requests.Session()
        self._session.headers.update(
            {
                "apikey": service_role_key,
                "Authorization": f"Bearer {service_role_key}",
                "Content-Type": "application/json",
            }
        )

    def _url(self, table: str) -> str:
        return f"{self._rest_url}/{table}"

    def select(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        resp = self._session.get(self._url(table), params=params, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    def insert(
        self, table: str, rows: list[dict[str, Any]], *, return_representation: bool = False
    ) -> list[dict[str, Any]]:
        if not rows:
            return []
        prefer = "return=representation" if return_representation else "return=minimal"
        resp = self._session.post(
            self._url(table),
            json=rows,
            headers={"Prefer": prefer},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json() if return_representation else []

    def update(
        self,
        table: str,
        filters: dict[str, str],
        patch: dict[str, Any],
        *,
        return_representation: bool = False,
    ) -> list[dict[str, Any]]:
        prefer = "return=representation" if return_representation else "return=minimal"
        resp = self._session.patch(
            self._url(table),
            params=filters,
            json=patch,
            headers={"Prefer": prefer},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json() if return_representation else []

    # --- helpers métier -----------------------------------------------------

    def fetch_pending_runs(self, limit: int = 5) -> list[dict[str, Any]]:
        """Runs en attente, les plus anciens d'abord."""
        return self.select(
            "runs",
            {
                "status": "eq.demande",
                "order": "created_at.asc",
                "limit": str(limit),
                "select": "*",
            },
        )

    def claim_run(self, run_id: str) -> dict[str, Any] | None:
        """Passe un run `demande` → `en_cours` de façon atomique.

        Le filtre `status=eq.demande` garantit qu'un seul worker l'attrape :
        si un autre l'a déjà pris, la mise à jour ne renvoie aucune ligne.
        """
        rows = self.update(
            "runs",
            {"id": f"eq.{run_id}", "status": "eq.demande"},
            {"status": "en_cours", "etape_courante": "Initialisation", "progress": 1},
            return_representation=True,
        )
        return rows[0] if rows else None

    def requeue_stale_runs(self, older_than_s: float) -> int:
        """Remet en file (`en_cours` → `demande`) les runs orphelins.

        Un run dont le worker est mort/redéployé en plein traitement reste figé
        en `en_cours` et n'est jamais repris (on ne ramasse que les `demande`).
        On le détecte par l'ancienneté de `updated_at` : pas de progrès depuis
        `older_than_s`. Renvoie le nombre de runs remis en file.
        """
        from datetime import timedelta

        cutoff = (
            datetime.now(timezone.utc) - timedelta(seconds=older_than_s)
        ).isoformat()
        rows = self.update(
            "runs",
            {"status": "eq.en_cours", "updated_at": f"lt.{cutoff}"},
            {
                "status": "demande",
                "etape_courante": "En attente (réamorcé après interruption)",
                "progress": 0,
            },
            return_representation=True,
        )
        return len(rows)

    def get_verticale(self, verticale_id: str | None) -> dict[str, Any] | None:
        if not verticale_id:
            return None
        rows = self.select(
            "verticales", {"id": f"eq.{verticale_id}", "select": "*", "limit": "1"}
        )
        return rows[0] if rows else None

    def update_run_progress(
        self, run_id: str, *, etape: str, progress: int, counts: dict[str, int]
    ) -> None:
        self.update(
            "runs",
            {"id": f"eq.{run_id}"},
            {"etape_courante": etape, "progress": progress, "counts": counts},
        )

    def insert_leads(self, rows: list[dict[str, Any]]) -> None:
        # Insertion par lots pour rester sous les limites de payload.
        for start in range(0, len(rows), 200):
            self.insert(table="leads", rows=rows[start : start + 200])

    def finalize_run(
        self,
        run_id: str,
        *,
        status: str,
        counts: dict[str, int],
        cout_eur: float,
        erreur: str | None = None,
    ) -> None:
        patch: dict[str, Any] = {
            "status": status,
            "counts": counts,
            "cout_eur": round(cout_eur, 2),
            "progress": 100 if status == "termine" else 0,
            "etape_courante": "Terminé" if status == "termine" else "Échec",
            "erreur": erreur,
        }
        self.update("runs", {"id": f"eq.{run_id}"}, patch)

    def heartbeat(
        self,
        *,
        mode: str,
        version: str | None = None,
        pending: int | None = None,
        last_error: str | None = None,
        keys: dict[str, bool] | None = None,
    ) -> None:
        """Écrit le battement de cœur du worker (table singleton worker_heartbeat).

        L'UI déduit la liveness du process de la fraîcheur de `last_seen_at`.
        `pending`/`last_error`/`keys` ne sont écrits que s'ils sont fournis (un
        échec de run ne doit pas réinitialiser le compteur de file, et inversement).
        """
        patch: dict[str, Any] = {"last_seen_at": _now_iso(), "mode": mode, "updated_at": _now_iso()}
        if version is not None:
            patch["version"] = version
        if pending is not None:
            patch["pending_runs"] = pending
        if last_error is not None:
            patch["last_error"] = last_error[:500]
            patch["last_error_at"] = _now_iso()
        if keys is not None:
            patch["keys"] = keys
        self.update("worker_heartbeat", {"id": "eq.main"}, patch)
