"""Tests pour `cli_rgpd.cleanup` — purge automatique sessions anciennes."""

from __future__ import annotations

import tarfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from renoboost_leads.cli_rgpd import cleanup


def _creer_session(data_dir: Path, nom: str, contenu: str = "x") -> Path:
    session = data_dir / "output" / nom
    session.mkdir(parents=True)
    (session / "etage1_decouverte.csv").write_text(contenu)
    return session


@pytest.fixture
def data_dir_3_sessions(tmp_path: Path) -> Path:
    _creer_session(tmp_path, "2020-01-15_1000_ancienne")
    _creer_session(tmp_path, "2025-12-01_1200_recente")
    _creer_session(tmp_path, "2026-05-15_0900_hier")
    _creer_session(tmp_path, "pas_une_date_valide")  # ignoré
    return tmp_path


def test_cleanup_dry_run_par_defaut_ne_touche_rien(data_dir_3_sessions: Path) -> None:
    fixe = datetime(2026, 5, 16, tzinfo=timezone.utc)
    rapport = cleanup(data_dir_3_sessions, older_than_days=365 * 3, now=fixe)
    assert rapport.mode == "dry-run"
    assert len(rapport.candidates) == 1
    assert rapport.candidates[0].session_path.name == "2020-01-15_1000_ancienne"
    assert rapport.actions_effectuees == 0
    assert (data_dir_3_sessions / "output" / "2020-01-15_1000_ancienne").exists()


def test_cleanup_delete_supprime_les_anciennes(data_dir_3_sessions: Path) -> None:
    # 2026-05-16 - 100 j → seuil 2026-02-05 ; 2020 + 2025-12 sont avant
    fixe = datetime(2026, 5, 16, tzinfo=timezone.utc)
    rapport = cleanup(
        data_dir_3_sessions, older_than_days=100, mode="delete", now=fixe
    )
    assert rapport.actions_effectuees == 2
    assert not (data_dir_3_sessions / "output" / "2020-01-15_1000_ancienne").exists()
    assert not (data_dir_3_sessions / "output" / "2025-12-01_1200_recente").exists()
    assert (data_dir_3_sessions / "output" / "2026-05-15_0900_hier").exists()
    assert rapport.octets_liberes > 0


def test_cleanup_archive_cree_targz_avant_suppression(data_dir_3_sessions: Path) -> None:
    fixe = datetime(2026, 5, 16, tzinfo=timezone.utc)
    rapport = cleanup(
        data_dir_3_sessions, older_than_days=365 * 3, mode="archive", now=fixe
    )
    assert rapport.actions_effectuees == 1
    archive_path = data_dir_3_sessions / "archives" / "2020-01-15_1000_ancienne.tar.gz"
    assert archive_path.exists()
    with tarfile.open(archive_path, "r:gz") as tar:
        names = tar.getnames()
        assert any("etage1_decouverte.csv" in n for n in names)
    assert not (data_dir_3_sessions / "output" / "2020-01-15_1000_ancienne").exists()


def test_cleanup_mode_invalide_leve_valueerror(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="mode invalide"):
        cleanup(tmp_path, mode="explode")


def test_cleanup_older_than_negatif_leve_valueerror(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=">= 0"):
        cleanup(tmp_path, older_than_days=-1)


def test_cleanup_data_dir_sans_output_retourne_rapport_vide(tmp_path: Path) -> None:
    rapport = cleanup(tmp_path, older_than_days=365)
    assert rapport.candidates == []
    assert rapport.actions_effectuees == 0


def test_cleanup_ignore_dossiers_avec_nom_non_dates(tmp_path: Path) -> None:
    (tmp_path / "output").mkdir()
    (tmp_path / "output" / "session_sans_date").mkdir()
    rapport = cleanup(tmp_path, older_than_days=0, mode="dry-run")
    assert rapport.candidates == []
