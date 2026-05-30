"""État historique des parkings déjà traités (SQLite local).

Stratégie « flag-not-drop » identique au module veille : on marque les parkings
déjà vus lors d'un run précédent sans les exclure, pour garder la visibilité sur
les ré-apparitions tout en pouvant filtrer côté lecture.

Fichier par défaut : `data/parkings_aper/etat_parkings.sqlite`.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import date
from pathlib import Path

from ..common.logger import get_logger

logger = get_logger(__name__)


class EtatHistoriqueParkings:
    """Mémoire persistante des parkings déjà traités (clé = identifiant stable)."""

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
                CREATE TABLE IF NOT EXISTS parkings_vus (
                    identifiant    TEXT PRIMARY KEY,
                    premiere_date  TEXT NOT NULL,
                    derniere_date  TEXT NOT NULL,
                    nb_vus         INTEGER NOT NULL DEFAULT 1
                )
                """
            )

    def deja_vu(self, identifiant: str) -> bool:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM parkings_vus WHERE identifiant = ?", (identifiant,)
            ).fetchone()
        return row is not None

    def marquer_vu(self, identifiant: str, jour: date) -> None:
        iso = jour.isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO parkings_vus (identifiant, premiere_date, derniere_date, nb_vus)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(identifiant) DO UPDATE SET
                    derniere_date = excluded.derniere_date,
                    nb_vus = nb_vus + 1
                """,
                (identifiant, iso, iso),
            )

    def stats(self) -> dict[str, int]:
        with self._lock, self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM parkings_vus").fetchone()[0]
        return {"parkings_uniques_vus": int(total)}
