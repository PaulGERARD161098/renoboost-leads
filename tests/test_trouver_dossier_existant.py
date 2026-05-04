"""Tests pour _trouver_dossier_existant (bug B2 corrige).

Bug B2 : la fonction ne detecte pas le dossier dans certains cas a cause d'un
matching strict (case-sensitive, sensible aux accents et aux espaces vs
underscores).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from renoboost_leads import cli


def _make_session_dir(base: Path, name: str) -> Path:
    """Helper : cree un faux dossier de session."""
    d = base / name
    d.mkdir(parents=True)
    return d


@pytest.fixture
def fake_output_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Patche PROJECT_ROOT pour pointer vers tmp_path et cree data/output."""
    output_dir = tmp_path / "data" / "output"
    output_dir.mkdir(parents=True)
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    return output_dir


class TestTrouverDossierExistant:
    """Verifie le matching robuste de _trouver_dossier_existant (bug B2)."""

    def test_match_simple(self, fake_output_dir: Path):
        """Match basique : client='bdr', dossier '2026-05-01_2242_bdr'."""
        target = _make_session_dir(fake_output_dir, "2026-05-01_2242_bdr")
        result = cli._trouver_dossier_existant("bdr")
        assert result == target

    def test_match_case_insensitive(self, fake_output_dir: Path):
        """BUG B2 : client='BdR' doit matcher dossier '..._bdr' (case insensitive)."""
        target = _make_session_dir(fake_output_dir, "2026-05-01_2242_bdr")
        result = cli._trouver_dossier_existant("BdR")
        assert result == target

    def test_match_espaces_vs_underscores(self, fake_output_dir: Path):
        """BUG B2 : client='Mon Client' doit matcher dossier '..._Mon_Client'."""
        target = _make_session_dir(fake_output_dir, "2026-05-01_2242_Mon_Client")
        result = cli._trouver_dossier_existant("Mon Client")
        assert result == target

    def test_match_avec_accents(self, fake_output_dir: Path):
        """BUG B2 : client='Herault' doit matcher dossier '..._Herault'."""
        target = _make_session_dir(fake_output_dir, "2026-05-01_2242_Herault")
        result = cli._trouver_dossier_existant("Herault")
        assert result == target

    def test_match_avec_accents_inverse(self, fake_output_dir: Path):
        """BUG B2 : client avec accent doit matcher dossier sans accent (et vice versa)."""
        target = _make_session_dir(fake_output_dir, "2026-05-01_2242_Herault")
        # Note : on simule un client_name avec accent (Herault avec É)
        # Le dossier sur disque est sans accent (cas typique sur Windows)
        result = cli._trouver_dossier_existant("H\u00e9rault")
        assert result == target

    def test_pas_de_faux_positif_substring(self, fake_output_dir: Path):
        """BUG B2 : client='X' ne doit PAS matcher dossier '..._XYZ' (faux positif endswith)."""
        _make_session_dir(fake_output_dir, "2026-05-01_2242_XYZ")
        result = cli._trouver_dossier_existant("X")
        assert result is None

    def test_dossier_output_inexistant_retourne_none(self, tmp_path: Path, monkeypatch):
        """Cas limite : pas de dossier data/output."""
        monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
        result = cli._trouver_dossier_existant("bdr")
        assert result is None

    def test_plusieurs_dossiers_retourne_le_plus_recent(self, fake_output_dir: Path):
        """Si plusieurs sessions pour le meme client, retourne le plus recent (tri lexical desc)."""
        _make_session_dir(fake_output_dir, "2026-04-15_1000_bdr")
        target = _make_session_dir(fake_output_dir, "2026-05-01_2242_bdr")
        _make_session_dir(fake_output_dir, "2026-04-30_0900_bdr")
        result = cli._trouver_dossier_existant("bdr")
        assert result == target
