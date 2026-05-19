"""Outil agent `sync_session` — pousse/tire une session vers le storage distant.

Expose au copilote Claude la capacité de synchroniser une session entre le
filesystem local et le bucket Supabase (ou no-op si STORAGE_BACKEND=local).

Cas d'usage typiques :
- Après un run en local : "sync ma session vers le cloud" → direction="up"
- Sur Streamlit Cloud : "récupère la session X que j'ai faite en local"
  → direction="down"
- Liste les sessions du bucket : `direction="list"`
"""

from __future__ import annotations

from typing import Literal


def sync_session(
    session_id: str | None = None,
    direction: Literal["up", "down", "list"] = "up",
) -> dict:
    """Synchronise une session avec le backend de stockage configuré.

    Args:
        session_id: identifiant de la session (requis pour up/down,
            ignoré pour list).
        direction: 'up' upload local→bucket, 'down' bucket→local,
            'list' énumère les sessions du bucket.
    """
    from ...storage import get_storage

    storage = get_storage()

    if direction == "list":
        return storage.list_remote_sessions()

    if not session_id:
        return {
            "error": "session_id requis pour direction 'up' ou 'down'",
            "direction": direction,
        }

    if direction == "up":
        return storage.upload_session(session_id)
    if direction == "down":
        return storage.download_session(session_id)

    return {"error": f"direction invalide : '{direction}' (up|down|list)"}


SCHEMAS = [
    {
        "name": "sync_session",
        "description": (
            "Synchronise une session entre le filesystem local et le bucket "
            "de stockage distant (Supabase Storage). Indispensable sur "
            "Streamlit Cloud où le filesystem est éphémère. En backend "
            "'local' (défaut), c'est un no-op qui renvoie skipped=True. "
            "Utilise direction='list' pour voir ce qui est dans le bucket "
            "sans rien modifier."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": (
                        "Identifiant de session à synchroniser (requis pour "
                        "'up' et 'down', ignoré pour 'list')."
                    ),
                },
                "direction": {
                    "type": "string",
                    "enum": ["up", "down", "list"],
                    "description": (
                        "'up' = local → bucket (après un run). "
                        "'down' = bucket → local (avant lecture). "
                        "'list' = énumérer les sessions du bucket."
                    ),
                    "default": "up",
                },
            },
            "required": ["direction"],
        },
    }
]

DISPATCH = {"sync_session": sync_session}
