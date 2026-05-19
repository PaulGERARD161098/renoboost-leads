"""Backend de persistance local — no-op : les sessions sont déjà sur disque.

Sert de fallback quand `STORAGE_BACKEND=local`. Implémente le protocole
`SessionStorage` mais ne fait rien d'utile sauf valider l'existence des
dossiers, pour que les outils agent et l'UI Streamlit aient un comportement
homogène sans branchement spécial.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..settings import PROJECT_ROOT


def _sessions_root() -> Path:
    return PROJECT_ROOT / "data" / "output"


class LocalSessionStorage:
    """Backend trivial : tout est déjà sur le disque local."""

    backend_name = "local"

    def upload_session(self, session_id: str) -> dict[str, Any]:
        dossier = _sessions_root() / session_id
        if not dossier.is_dir():
            return {"error": f"session inconnue : '{session_id}'", "backend": "local"}
        return {
            "backend": "local",
            "session_id": session_id,
            "ok": True,
            "skipped": True,
            "reason": "backend local : pas de remote, session déjà sur disque",
        }

    def download_session(self, session_id: str) -> dict[str, Any]:
        dossier = _sessions_root() / session_id
        if not dossier.is_dir():
            return {
                "error": f"session inconnue : '{session_id}'",
                "backend": "local",
            }
        return {
            "backend": "local",
            "session_id": session_id,
            "ok": True,
            "skipped": True,
        }

    def list_remote_sessions(self) -> dict[str, Any]:
        root = _sessions_root()
        if not root.exists():
            return {"backend": "local", "sessions": []}
        ids = sorted(
            (d.name for d in root.iterdir() if d.is_dir()), reverse=True
        )
        return {"backend": "local", "sessions": ids}

    def delete_remote_session(self, session_id: str) -> dict[str, Any]:
        return {
            "backend": "local",
            "session_id": session_id,
            "ok": True,
            "skipped": True,
            "reason": "backend local : pas de remote à supprimer",
        }
