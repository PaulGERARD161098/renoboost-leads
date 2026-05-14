"""Tests état historique SIREN-déjà-vu-en-VE (SQLite)."""

from __future__ import annotations

from datetime import date

from renoboost_leads.veille_immatriculations.etat_historique import EtatHistoriqueVE


class TestEtatHistoriqueVE:
    def test_siren_inconnu_pas_deja_vu(self, tmp_path):
        etat = EtatHistoriqueVE(tmp_path / "etat.sqlite")
        assert etat.deja_vu("402111111") is False

    def test_marquer_puis_deja_vu(self, tmp_path):
        etat = EtatHistoriqueVE(tmp_path / "etat.sqlite")
        etat.marquer_vu("402111111", date(2026, 5, 13))
        assert etat.deja_vu("402111111") is True

    def test_marquer_idempotent_meme_date(self, tmp_path):
        etat = EtatHistoriqueVE(tmp_path / "etat.sqlite")
        etat.marquer_vu("402111111", date(2026, 5, 13))
        etat.marquer_vu("402111111", date(2026, 5, 13))
        assert etat.stats()["siren_uniques_avec_ve"] == 1

    def test_derniere_date_avance(self, tmp_path):
        etat = EtatHistoriqueVE(tmp_path / "etat.sqlite")
        etat.marquer_vu("402111111", date(2026, 1, 15))
        etat.marquer_vu("402111111", date(2026, 5, 13))
        # On vérifie via une lecture SQL directe
        import sqlite3

        with sqlite3.connect(etat.db_path) as conn:
            row = conn.execute(
                "SELECT premiere_date, derniere_date, nb_vus FROM siren_ve_vus "
                "WHERE siren = ?",
                ("402111111",),
            ).fetchone()
        assert row == ("2026-01-15", "2026-05-13", 2)

    def test_stats_compte_distinct(self, tmp_path):
        etat = EtatHistoriqueVE(tmp_path / "etat.sqlite")
        etat.marquer_vu("111111111", date(2026, 5, 13))
        etat.marquer_vu("222222222", date(2026, 5, 13))
        etat.marquer_vu("111111111", date(2026, 5, 14))
        assert etat.stats()["siren_uniques_avec_ve"] == 2

    def test_persistance_entre_instances(self, tmp_path):
        db = tmp_path / "etat.sqlite"
        EtatHistoriqueVE(db).marquer_vu("402111111", date(2026, 5, 13))
        # Nouvelle instance pointant sur le même fichier
        assert EtatHistoriqueVE(db).deja_vu("402111111") is True
