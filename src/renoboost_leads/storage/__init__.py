"""Persistance des sessions de prospection — abstraction backend.

Permet de stocker les sessions (`data/output/<session_id>/`) :
- en local uniquement (`STORAGE_BACKEND=local`, par défaut) ;
- ou sur Supabase Storage (`STORAGE_BACKEND=supabase`) en miroir du local,
  ce qui rend les sessions persistantes face au filesystem éphémère de
  Streamlit Cloud.

Le backend Supabase upload/download des **tar.gz** du dossier complet de la
session (CSVs + run_stats.json + config_snapshot.yaml + rapport.html...).
Une session = un objet `<session_id>.tar.gz` dans le bucket.

Usage typique :
    from renoboost_leads.storage import get_storage
    storage = get_storage()
    storage.upload_session("recherche-2026-05-19")
    storage.list_remote_sessions()
"""

from __future__ import annotations

from typing import Any, Protocol


class SessionStorage(Protocol):
    """Contrat des backends de persistance.

    Toutes les méthodes renvoient un dict sérialisable JSON pour faciliter
    l'exposition en outils agent et l'affichage Streamlit.
    """

    def upload_session(self, session_id: str) -> dict[str, Any]:
        """Pousse le dossier `data/output/<session_id>/` vers le backend."""
        ...

    def download_session(self, session_id: str) -> dict[str, Any]:
        """Récupère la session depuis le backend vers `data/output/`."""
        ...

    def list_remote_sessions(self) -> dict[str, Any]:
        """Liste les session_ids disponibles côté backend."""
        ...

    def delete_remote_session(self, session_id: str) -> dict[str, Any]:
        """Supprime la session côté backend (le local n'est pas touché)."""
        ...


def get_storage() -> SessionStorage:
    """Renvoie l'implémentation active selon `settings.storage_backend`.

    - `local` (défaut) → no-op, les sessions restent dans `data/output/`.
    - `supabase` → utilise SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY.
      Échoue avec un message clair si la conf est incomplète.
    """
    from ..settings import get_settings

    settings = get_settings()
    if settings.storage_backend == "supabase":
        from .supabase_backend import SupabaseSessionStorage

        return SupabaseSessionStorage.from_settings(settings)
    from .local import LocalSessionStorage

    return LocalSessionStorage()


__all__ = ["SessionStorage", "get_storage"]
