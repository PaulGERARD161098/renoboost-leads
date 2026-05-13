"""État historique SIREN-déjà-vu-en-VE (SQLite local).

Stratégie "flag-not-drop" : on marque les SIREN qui ont déjà été observés
dans un VE auparavant, sans les exclure du flux. L'utilisateur peut alors
décider en aval (UI, mail, CSV) de les traiter différemment.

Fichier par défaut : `data/veille/etat_siren_ve.sqlite`.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import date
from pathlib import Path

from ..common.logger import get_logger

logger = get_logger(__name__)


class EtatHistoriqueVE:
    """Mémoire persistante des SIREN ayant déjà eu un VE.

    Une seule table : `siren_ve_vus` (siren TEXT PK, premiere_date TEXT, derniere_date TEXT).
    """

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
                CREATE TABLE IF NOT EXISTS siren_ve_vus (
                    siren          TEXT PRIMARY KEY,
                    premiere_date  TEXT NOT NULL,
                    derniere_date  TEXT NOT NULL,
                    nb_vus         INTEGER NOT NULL DEFAULT 1
                )
                """
            )

    def deja_vu(self, siren: str) -> bool:
        """True si ce SIREN a déjà été observé en VE (avant l'appel courant)."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM siren_ve_vus WHERE siren = ?", (siren,)
            ).fetchone()
        return row is not None

    def marquer_vu(self, siren: str, date_immat: date) -> None:
        """Marque un SIREN comme vu (INSERT ou UPDATE).

        Si nouvelle entrée : premiere_date = derniere_date = date_immat, nb_vus = 1.
        Si déjà connu : derniere_date = max(actuelle, date_immat), nb_vus += 1.
        """
        iso = date_immat.isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO siren_ve_vus (siren, premiere_date, derniere_date, nb_vus)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(siren) DO UPDATE SET
                    derniere_date = CASE
                        WHEN excluded.derniere_date > derniere_date THEN excluded.derniere_date
                        ELSE derniere_date
                    END,
                    nb_vus = nb_vus + 1
                """,
                (siren, iso, iso),
            )

    def stats(self) -> dict[str, int]:
        with self._lock, self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM siren_ve_vus").fetchone()[0]
        return {"siren_uniques_avec_ve": int(total)}
