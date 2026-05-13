"""Cache L4 — stocke les réponses Claude pour éviter de re-payer.

Stratégie d'invalidation :
- La clé de cache contient un hash de
  (prompt_version, modèle, contexte_client, inclure_pitch).
- Si l'un de ces paramètres change, le cache est considéré invalide
  pour les leads concernés (cache miss → nouvel appel).
- Pas de TTL : un score est valable tant que le prompt ne bouge pas.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from ..common.logger import get_logger

logger = get_logger(__name__)


def calcul_cache_key(
    prompt_version: str,
    modele: str,
    contexte_client: str,
    inclure_pitch: bool,
) -> str:
    """Hash stable des paramètres qui rendent un score valide.

    Sortie : un sha256 court (16 hex chars), lisible dans les logs.
    """
    payload = json.dumps(
        {
            "prompt_version": prompt_version,
            "modele": modele,
            "contexte_client": contexte_client,
            "inclure_pitch": inclure_pitch,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class CacheStage4:
    """Cache SQLite dédié L4. Stocké à côté du `cache.sqlite` de session."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stage4_results (
                    place_id    TEXT NOT NULL,
                    cache_key   TEXT NOT NULL,
                    payload     TEXT NOT NULL,
                    created_at  REAL NOT NULL DEFAULT (julianday('now')),
                    PRIMARY KEY (place_id, cache_key)
                )
                """
            )

    def get(self, place_id: str, cache_key: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM stage4_results WHERE place_id = ? AND cache_key = ?",
                (place_id, cache_key),
            ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            logger.warning("Cache L4 corrompu pour place_id=%s (ignoré)", place_id)
            return None

    def store(self, place_id: str, cache_key: str, payload: dict[str, Any]) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO stage4_results "
                "(place_id, cache_key, payload) VALUES (?, ?, ?)",
                (place_id, cache_key, json.dumps(payload, ensure_ascii=False, default=str)),
            )

    def count(self, cache_key: str | None = None) -> int:
        with self._lock, self._connect() as conn:
            if cache_key:
                row = conn.execute(
                    "SELECT COUNT(*) FROM stage4_results WHERE cache_key = ?",
                    (cache_key,),
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) FROM stage4_results").fetchone()
        return int(row[0]) if row else 0
