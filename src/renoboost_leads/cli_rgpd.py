"""Logique pure pour les commandes RGPD `forget` et `cleanup`.

Aucune dépendance Click : tout est testable directement via appels Python.
"""

from __future__ import annotations

import csv
import re
import shutil
import sqlite3
import tarfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

EFFACEMENTS_LOG_FILENAME = "effacements_log.csv"
EFFACEMENTS_LOG_COLUMNS = [
    "date_iso",
    "identifiant_type",
    "identifiant_valeur",
    "sessions_touchees",
    "lignes_effacees",
    "motif",
]

CACHE_FILES = ("cache.sqlite", "cache_l3_5.sqlite", "cache_l4.sqlite")
CACHE_TABLES = {
    "cache.sqlite": "place_results",
    "cache_l3_5.sqlite": "stage3_5_results",
    "cache_l4.sqlite": "stage4_results",
}

SESSION_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


@dataclass
class ForgetSessionReport:
    session_path: Path
    lignes_effacees: int = 0
    csvs_modifies: list[str] = field(default_factory=list)
    place_ids_effaces_cache: int = 0


@dataclass
class ForgetReport:
    sessions: list[ForgetSessionReport] = field(default_factory=list)
    dry_run: bool = False

    @property
    def total_lignes(self) -> int:
        return sum(s.lignes_effacees for s in self.sessions)

    @property
    def sessions_touchees(self) -> int:
        return sum(1 for s in self.sessions if s.lignes_effacees > 0)


@dataclass
class CleanupCandidate:
    session_path: Path
    date_session: datetime
    taille_octets: int


@dataclass
class CleanupReport:
    mode: str
    seuil_jours: int
    candidates: list[CleanupCandidate] = field(default_factory=list)
    actions_effectuees: int = 0
    octets_liberes: int = 0


# ─── Helpers internes ──────────────────────────────────────────────────────────


def _split_pipe(value: str) -> list[str]:
    return [v for v in (value or "").split("|") if v]


def _row_matches(
    row: dict[str, str],
    *,
    email: str | None,
    siren: str | None,
    place_id: str | None,
) -> bool:
    """OR logic : match si au moins un critère renseigné correspond."""
    if place_id and (row.get("place_id") or "").strip() == place_id:
        return True
    if siren and (row.get("siren") or "").strip() == siren:
        return True
    if email:
        email_lc = email.strip().lower()
        for col in ("email_dropcontact",):
            if (row.get(col) or "").strip().lower() == email_lc:
                return True
        for col in ("emails_verifies", "emails_candidats"):
            emails = [e.strip().lower() for e in _split_pipe(row.get(col, ""))]
            if email_lc in emails:
                return True
    return False


def _filter_csv(
    csv_path: Path,
    *,
    email: str | None,
    siren: str | None,
    place_id: str | None,
    dry_run: bool,
) -> tuple[int, list[str]]:
    """Réécrit `csv_path` sans les lignes matchant. Retourne (nb_effaces, place_ids_supprimes)."""
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    kept: list[dict[str, str]] = []
    purged_place_ids: list[str] = []
    for row in rows:
        if _row_matches(row, email=email, siren=siren, place_id=place_id):
            pid = (row.get("place_id") or "").strip()
            if pid:
                purged_place_ids.append(pid)
        else:
            kept.append(row)

    nb_effaces = len(rows) - len(kept)
    if nb_effaces > 0 and not dry_run:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(kept)
    return nb_effaces, purged_place_ids


def _purge_caches(
    session_path: Path, place_ids: set[str], *, dry_run: bool
) -> int:
    """DELETE des entrées matchant place_ids dans les 3 caches SQLite."""
    if not place_ids:
        return 0
    total_supprime = 0
    for cache_file, table in CACHE_TABLES.items():
        db_path = session_path / cache_file
        if not db_path.exists():
            continue
        placeholders = ",".join("?" * len(place_ids))
        # table = const interne (CACHE_TABLES), pas d'input externe — S608 ok.
        sql_count = f"SELECT COUNT(*) FROM {table} WHERE place_id IN ({placeholders})"  # noqa: S608
        sql_delete = f"DELETE FROM {table} WHERE place_id IN ({placeholders})"  # noqa: S608
        with sqlite3.connect(db_path) as conn:
            try:
                nb = conn.execute(sql_count, tuple(place_ids)).fetchone()[0]
            except sqlite3.OperationalError:
                continue  # table absente (cache jamais utilisé)
            total_supprime += nb
            if nb > 0 and not dry_run:
                conn.execute(sql_delete, tuple(place_ids))
    return total_supprime


def _iter_session_csvs(session_path: Path) -> list[Path]:
    """Tous les CSV étage de la session + backups associés."""
    paths: list[Path] = []
    for pattern in ("etage*.csv",):
        paths.extend(sorted(session_path.glob(pattern)))
    backups = session_path / "backups"
    if backups.exists():
        paths.extend(sorted(backups.glob("etage*.csv")))
    return paths


def _append_effacement_log(
    data_dir: Path,
    *,
    identifiant_type: str,
    identifiant_valeur: str,
    sessions_touchees: int,
    lignes_effacees: int,
    motif: str,
) -> None:
    log_path = data_dir / EFFACEMENTS_LOG_FILENAME
    is_new = not log_path.exists()
    data_dir.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EFFACEMENTS_LOG_COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow(
            {
                "date_iso": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "identifiant_type": identifiant_type,
                "identifiant_valeur": identifiant_valeur,
                "sessions_touchees": sessions_touchees,
                "lignes_effacees": lignes_effacees,
                "motif": motif,
            }
        )


# ─── API publique ──────────────────────────────────────────────────────────────


def forget(
    data_dir: Path,
    *,
    email: str | None = None,
    siren: str | None = None,
    place_id: str | None = None,
    motif: str = "demande RGPD",
    dry_run: bool = False,
) -> ForgetReport:
    """Efface un lead identifié par email/SIREN/place_id dans toutes les sessions.

    Au moins un critère doit être renseigné. Logique OR : match si au moins un
    critère correspond. Mode `dry_run=True` n'écrit rien.
    """
    if not any([email, siren, place_id]):
        raise ValueError("Au moins un critère (--email, --siren, --place-id) est requis")

    report = ForgetReport(dry_run=dry_run)
    output_root = data_dir / "output"
    if not output_root.exists():
        return report

    for session_path in sorted(output_root.iterdir()):
        if not session_path.is_dir():
            continue
        s_report = ForgetSessionReport(session_path=session_path)
        all_place_ids: set[str] = set()
        for csv_path in _iter_session_csvs(session_path):
            nb, pids = _filter_csv(
                csv_path, email=email, siren=siren, place_id=place_id, dry_run=dry_run
            )
            if nb > 0:
                s_report.lignes_effacees += nb
                s_report.csvs_modifies.append(str(csv_path.relative_to(session_path)))
                all_place_ids.update(pids)
        if all_place_ids or place_id:
            ids_to_purge = all_place_ids | ({place_id} if place_id else set())
            s_report.place_ids_effaces_cache = _purge_caches(
                session_path, ids_to_purge, dry_run=dry_run
            )
        report.sessions.append(s_report)

    if not dry_run and report.total_lignes > 0:
        types_actifs = [
            label
            for label, value in (
                ("email", email),
                ("siren", siren),
                ("place_id", place_id),
            )
            if value
        ]
        valeurs = [
            f"{label}={value}"
            for label, value in (
                ("email", email),
                ("siren", siren),
                ("place_id", place_id),
            )
            if value
        ]
        _append_effacement_log(
            data_dir,
            identifiant_type="+".join(types_actifs),
            identifiant_valeur=";".join(valeurs),
            sessions_touchees=report.sessions_touchees,
            lignes_effacees=report.total_lignes,
            motif=motif,
        )

    return report


def _parse_session_date(session_name: str) -> datetime | None:
    m = SESSION_DATE_RE.match(session_name)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
    except ValueError:
        return None


def _dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def cleanup(
    data_dir: Path,
    *,
    older_than_days: int = 365 * 3,
    mode: str = "dry-run",
    now: datetime | None = None,
) -> CleanupReport:
    """Liste / archive / supprime les sessions plus anciennes que N jours.

    Modes :
    - `dry-run` (défaut) : retourne la liste, ne touche à rien
    - `archive` : tar.gz dans `data/archives/<nom>.tar.gz` puis supprime la session
    - `delete` : supprime la session directement
    """
    if mode not in ("dry-run", "archive", "delete"):
        raise ValueError(f"mode invalide : {mode}")
    if older_than_days < 0:
        raise ValueError("older_than_days doit être >= 0")

    report = CleanupReport(mode=mode, seuil_jours=older_than_days)
    output_root = data_dir / "output"
    if not output_root.exists():
        return report

    now = now or datetime.now(timezone.utc)
    seuil = now.timestamp() - older_than_days * 86400

    for session_path in sorted(output_root.iterdir()):
        if not session_path.is_dir():
            continue
        date_session = _parse_session_date(session_path.name)
        if date_session is None:
            continue
        if date_session.timestamp() >= seuil:
            continue
        taille = _dir_size(session_path)
        report.candidates.append(
            CleanupCandidate(
                session_path=session_path,
                date_session=date_session,
                taille_octets=taille,
            )
        )

    if mode == "dry-run":
        return report

    archives_dir = data_dir / "archives"
    for c in report.candidates:
        if mode == "archive":
            archives_dir.mkdir(parents=True, exist_ok=True)
            archive_path = archives_dir / f"{c.session_path.name}.tar.gz"
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(c.session_path, arcname=c.session_path.name)
        shutil.rmtree(c.session_path)
        report.actions_effectuees += 1
        report.octets_liberes += c.taille_octets

    return report
