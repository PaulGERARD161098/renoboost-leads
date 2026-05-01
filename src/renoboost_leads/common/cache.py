"""Cache local SQLite — permet de reprendre un run interrompu.

Stocke les `place_id` déjà traités (et leur résultat) pour éviter de re-payer
des appels API en cas de crash / reprise.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .logger import get_logger

logger = get_logger(__name__)


class SessionCache:
    """Cache SQLite persistant (par session_id)."""

    def __init__(self, cache_path: Path):
        self.cache_path = cache_path
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.cache_path, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS place_results (
                    place_id   TEXT PRIMARY KEY,
                    stage      TEXT NOT NULL,
                    payload    TEXT NOT NULL,
                    created_at REAL NOT NULL DEFAULT (julianday('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS searches_done (
                    search_key TEXT PRIMARY KEY,
                    nb_results INTEGER NOT NULL,
                    created_at REAL NOT NULL DEFAULT (julianday('now'))
                )
                """
            )

    # ─── Recherches déjà effectuées (pour ne pas refaire un Text Search) ───

    def search_done(self, search_key: str) -> bool:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM searches_done WHERE search_key = ?", (search_key,)
            ).fetchone()
            return row is not None

    def mark_search_done(self, search_key: str, nb_results: int) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO searches_done (search_key, nb_results) VALUES (?, ?)",
                (search_key, nb_results),
            )

    # ─── Résultats Place Details (pour ne pas re-payer un GetPlace) ───

    def get_place(self, place_id: str, stage: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM place_results WHERE place_id = ? AND stage = ?",
                (place_id, stage),
            ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            logger.warning("Cache corrompu pour place_id=%s (ignoré)", place_id)
            return None

    def store_place(self, place_id: str, stage: str, payload: dict[str, Any]) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO place_results (place_id, stage, payload) VALUES (?, ?, ?)",
                (place_id, stage, json.dumps(payload, ensure_ascii=False, default=str)),
            )

    def count_places(self, stage: str | None = None) -> int:
        with self._lock, self._connect() as conn:
            if stage:
                row = conn.execute(
                    "SELECT COUNT(*) FROM place_results WHERE stage = ?", (stage,)
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) FROM place_results").fetchone()
        return int(row[0]) if row else 0
