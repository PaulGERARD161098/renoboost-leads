"""Tests pour lire_stage1_csv (bug B3 corrige).

Bug B3 : message d'erreur peu clair quand le CSV est introuvable.
Distinction necessaire entre :
- dossier parent inexistant (session inconnue)
- dossier existe mais CSV absent (L1 pas execute ou CSV supprime)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from renoboost_leads.exporter import lire_stage1_csv


class TestLireStage1CsvErreurs:
    """Verifie que les messages d'erreur sont actionnables (bug B3)."""

    def test_dossier_parent_inexistant_message_clair(self, tmp_path: Path):
        """Quand le dossier de session n'existe pas."""
        csv_path = tmp_path / "session_inconnue" / "etage1_decouverte.csv"
        with pytest.raises(FileNotFoundError) as exc_info:
            lire_stage1_csv(csv_path)
        msg = str(exc_info.value)
        assert "Dossier de session introuvable" in msg
        assert str(csv_path.parent) in msg

    def test_dossier_existe_csv_absent_liste_fichiers(self, tmp_path: Path):
        """Quand le dossier existe mais pas le CSV."""
        session_dir = tmp_path / "session_active"
        session_dir.mkdir()
        (session_dir / "config.yaml").write_text("nom: test", encoding="utf-8")
        (session_dir / "etage2_entreprises.csv").write_text("col1\n", encoding="utf-8")

        csv_path = session_dir / "etage1_decouverte.csv"
        with pytest.raises(FileNotFoundError) as exc_info:
            lire_stage1_csv(csv_path)
        msg = str(exc_info.value)
        assert "introuvable" in msg
        assert "etage2_entreprises.csv" in msg
        assert "config.yaml" in msg

    def test_dossier_existe_vide_message_explicite(self, tmp_path: Path):
        """Quand le dossier existe mais est vide."""
        session_dir = tmp_path / "session_vide"
        session_dir.mkdir()
        csv_path = session_dir / "etage1_decouverte.csv"
        with pytest.raises(FileNotFoundError) as exc_info:
            lire_stage1_csv(csv_path)
        msg = str(exc_info.value)
        assert "dossier vide" in msg.lower()
