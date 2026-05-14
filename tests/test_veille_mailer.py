"""Tests du module mailer (construction du message, pas l'envoi réseau)."""

from __future__ import annotations

from pathlib import Path

from renoboost_leads.veille_immatriculations.mailer import (
    ConfigSMTP,
    ResumeVeille,
    _construire_corps_html,
    _construire_corps_texte,
    _construire_message,
)


def _config_factice() -> ConfigSMTP:
    return ConfigSMTP(
        host="smtp.test",
        port=587,
        user="user@test.fr",
        password="x",  # noqa: S106 — placeholder de test, pas un secret réel
        expediteur="from@test.fr",
        destinataires=["a@test.fr", "b@test.fr"],
    )


def _resume_factice(tmp_path: Path) -> ResumeVeille:
    csv = tmp_path / "veille.csv"
    csv.write_text("nom;siren\nTEST;402111111\n", encoding="utf-8")
    return ResumeVeille(
        date_run="2026-05-13",
        nb_lignes_brutes=120,
        nb_ve_flotte=87,
        nb_nouveaux=64,
        nb_deja_vus=23,
        nb_top_leads=12,
        cout_l4_eur=0.4789,
        chemin_csv=csv,
        extraits_top=[
            {
                "nom": "SMI Industrie",
                "siren": "402111111",
                "score": "89",
                "raison": "PME mécanique cible",
            }
        ],
    )


class TestCorpsTexte:
    def test_inclut_kpis(self, tmp_path):
        texte = _construire_corps_texte(_resume_factice(tmp_path))
        assert "2026-05-13" in texte
        assert "120" in texte
        assert "87" in texte
        assert "12" in texte
        assert "0.4789" in texte

    def test_inclut_extraits_top(self, tmp_path):
        texte = _construire_corps_texte(_resume_factice(tmp_path))
        assert "SMI Industrie" in texte
        assert "402111111" in texte
        assert "89" in texte


class TestCorpsHTML:
    def test_inclut_tableau_html(self, tmp_path):
        html = _construire_corps_html(_resume_factice(tmp_path))
        assert "<table" in html
        assert "SMI Industrie" in html
        assert "<b>89</b>" in html


class TestConstruireMessage:
    def test_message_avec_piece_jointe(self, tmp_path):
        cfg = _config_factice()
        resume = _resume_factice(tmp_path)
        msg = _construire_message(cfg, resume)

        assert msg["From"] == "from@test.fr"
        assert "a@test.fr" in msg["To"]
        assert "b@test.fr" in msg["To"]
        assert "2026-05-13" in msg["Subject"]
        assert "12 top leads" in msg["Subject"]

        # Vérifier qu'il y a bien une pièce jointe CSV
        pieces = list(msg.iter_attachments())
        assert len(pieces) == 1
        assert pieces[0].get_filename() == "veille.csv"

    def test_message_sans_extraits_pas_de_table(self, tmp_path):
        resume = _resume_factice(tmp_path)
        resume.extraits_top = []
        msg = _construire_message(_config_factice(), resume)
        # Le corps HTML ne doit pas contenir de table
        parts = list(msg.walk())
        html_parts = [p for p in parts if p.get_content_type() == "text/html"]
        assert html_parts
        for p in html_parts:
            assert "<table" not in p.get_content()
