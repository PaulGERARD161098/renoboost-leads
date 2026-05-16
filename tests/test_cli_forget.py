"""Tests pour `cli_rgpd.forget` — droit à l'effacement RGPD."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

import pytest

from renoboost_leads.cli_rgpd import EFFACEMENTS_LOG_FILENAME, forget


def _ecrire_csv(path: Path, lignes: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(lignes[0].keys()) if lignes else ["place_id"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(lignes)


def _lire_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _init_cache(path: Path, table: str, place_ids: list[str]) -> None:
    # table = const interne au test, pas d'input externe — S608 ok.
    with sqlite3.connect(path) as conn:
        if table == "place_results":
            conn.execute(
                f"CREATE TABLE {table} (place_id TEXT PRIMARY KEY, "  # noqa: S608
                "stage TEXT, payload TEXT)"
            )
            for pid in place_ids:
                conn.execute(
                    f"INSERT INTO {table} VALUES (?, 'L1', '{{}}')", (pid,)  # noqa: S608
                )
        else:
            conn.execute(
                f"CREATE TABLE {table} (place_id TEXT, cache_key TEXT, payload TEXT, "  # noqa: S608
                "PRIMARY KEY (place_id, cache_key))"
            )
            for pid in place_ids:
                conn.execute(
                    f"INSERT INTO {table} VALUES (?, 'k1', '{{}}')", (pid,)  # noqa: S608
                )


def _compter_cache(path: Path, table: str) -> int:
    with sqlite3.connect(path) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608


@pytest.fixture
def data_dir_avec_session(tmp_path: Path) -> Path:
    """Crée un data/ avec 1 session contenant 3 leads sur tous les étages + caches."""
    session = tmp_path / "output" / "2026-05-16_1000_test"
    session.mkdir(parents=True)

    _ecrire_csv(
        session / "etage1_decouverte.csv",
        [
            {"place_id": "P001", "nom_etablissement": "A"},
            {"place_id": "P002", "nom_etablissement": "B"},
            {"place_id": "P003", "nom_etablissement": "C"},
        ],
    )
    _ecrire_csv(
        session / "etage2_entreprises.csv",
        [
            {"place_id": "P001", "siren": "111111111", "nom_etablissement": "A"},
            {"place_id": "P002", "siren": "222222222", "nom_etablissement": "B"},
            {"place_id": "P003", "siren": "333333333", "nom_etablissement": "C"},
        ],
    )
    _ecrire_csv(
        session / "etage3_contacts.csv",
        [
            {
                "place_id": "P001",
                "siren": "111111111",
                "emails_verifies": "contact@a.fr|info@a.fr",
                "emails_candidats": "",
            },
            {
                "place_id": "P002",
                "siren": "222222222",
                "emails_verifies": "",
                "emails_candidats": "patron@b.fr",
            },
            {
                "place_id": "P003",
                "siren": "333333333",
                "emails_verifies": "x@c.fr",
                "emails_candidats": "",
            },
        ],
    )
    _ecrire_csv(
        session / "etage3_5_dropcontact.csv",
        [
            {"place_id": "P001", "siren": "111111111", "email_dropcontact": "ceo@a.fr"},
            {"place_id": "P002", "siren": "222222222", "email_dropcontact": ""},
        ],
    )
    # backups : version horodatée du CSV L1
    _ecrire_csv(
        session / "backups" / "etage1_decouverte_20260516_100500.csv",
        [
            {"place_id": "P001", "nom_etablissement": "A"},
            {"place_id": "P002", "nom_etablissement": "B"},
            {"place_id": "P003", "nom_etablissement": "C"},
        ],
    )
    # caches
    _init_cache(session / "cache.sqlite", "place_results", ["P001", "P002", "P003"])
    _init_cache(session / "cache_l3_5.sqlite", "stage3_5_results", ["P001", "P002"])
    _init_cache(session / "cache_l4.sqlite", "stage4_results", ["P001"])
    return tmp_path


def test_forget_sans_critere_leve_valueerror(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="critère"):
        forget(tmp_path)


def test_forget_par_place_id_efface_csv_et_cache(data_dir_avec_session: Path) -> None:
    rapport = forget(data_dir_avec_session, place_id="P001")

    assert rapport.dry_run is False
    assert rapport.total_lignes == 5  # L1+L2+L3+L3.5+backup = 5 lignes
    assert rapport.sessions_touchees == 1
    session = data_dir_avec_session / "output" / "2026-05-16_1000_test"
    assert len(_lire_csv(session / "etage1_decouverte.csv")) == 2
    assert len(_lire_csv(session / "etage3_5_dropcontact.csv")) == 1
    assert _compter_cache(session / "cache.sqlite", "place_results") == 2
    assert _compter_cache(session / "cache_l3_5.sqlite", "stage3_5_results") == 1
    assert _compter_cache(session / "cache_l4.sqlite", "stage4_results") == 0


def test_forget_par_email_dans_emails_verifies(data_dir_avec_session: Path) -> None:
    rapport = forget(data_dir_avec_session, email="contact@a.fr")
    assert rapport.total_lignes >= 1
    session = data_dir_avec_session / "output" / "2026-05-16_1000_test"
    lignes_l3 = _lire_csv(session / "etage3_contacts.csv")
    assert all(r["place_id"] != "P001" for r in lignes_l3)


def test_forget_par_email_dropcontact(data_dir_avec_session: Path) -> None:
    rapport = forget(data_dir_avec_session, email="ceo@a.fr")
    assert rapport.total_lignes == 1
    session = data_dir_avec_session / "output" / "2026-05-16_1000_test"
    assert len(_lire_csv(session / "etage3_5_dropcontact.csv")) == 1


def test_forget_par_siren(data_dir_avec_session: Path) -> None:
    rapport = forget(data_dir_avec_session, siren="222222222")
    assert rapport.total_lignes >= 3  # L2 + L3 + L3.5 + backups (pas L1 sans siren)
    session = data_dir_avec_session / "output" / "2026-05-16_1000_test"
    assert all(r["siren"] != "222222222" for r in _lire_csv(session / "etage2_entreprises.csv"))


def test_forget_dry_run_ne_modifie_rien(data_dir_avec_session: Path) -> None:
    rapport = forget(data_dir_avec_session, place_id="P001", dry_run=True)
    assert rapport.dry_run is True
    assert rapport.total_lignes == 5
    session = data_dir_avec_session / "output" / "2026-05-16_1000_test"
    assert len(_lire_csv(session / "etage1_decouverte.csv")) == 3
    assert _compter_cache(session / "cache.sqlite", "place_results") == 3
    assert not (data_dir_avec_session / EFFACEMENTS_LOG_FILENAME).exists()


def test_forget_ecrit_log_effacements(data_dir_avec_session: Path) -> None:
    forget(data_dir_avec_session, place_id="P001", motif="droit oubli client X")
    log_path = data_dir_avec_session / EFFACEMENTS_LOG_FILENAME
    assert log_path.exists()
    lignes = _lire_csv(log_path)
    assert len(lignes) == 1
    assert lignes[0]["identifiant_type"] == "place_id"
    assert lignes[0]["identifiant_valeur"] == "place_id=P001"
    assert lignes[0]["motif"] == "droit oubli client X"
    assert int(lignes[0]["lignes_effacees"]) == 5


def test_forget_aucun_match_ne_log_rien(data_dir_avec_session: Path) -> None:
    rapport = forget(data_dir_avec_session, place_id="INEXISTANT")
    assert rapport.total_lignes == 0
    assert not (data_dir_avec_session / EFFACEMENTS_LOG_FILENAME).exists()


def test_forget_data_dir_sans_output_retourne_rapport_vide(tmp_path: Path) -> None:
    rapport = forget(tmp_path, place_id="P001")
    assert rapport.sessions == []
    assert rapport.total_lignes == 0
