"""Tests Phase D — email récapitulatif parkings APER (construction du message)."""

from __future__ import annotations

from pathlib import Path

from renoboost_leads.parkings_aper.mailer import (
    ResumeAper,
    _construire_message,
    _corps_html,
    _corps_texte,
)
from renoboost_leads.veille_immatriculations.mailer import ConfigSMTP


def _config() -> ConfigSMTP:
    return ConfigSMTP(
        host="smtp.test",
        port=587,
        user="user@test.fr",
        password="x",  # noqa: S106 — placeholder de test
        expediteur="from@test.fr",
        destinataires=["a@test.fr", "b@test.fr"],
    )


def _resume(tmp_path: Path) -> ResumeAper:
    csv = tmp_path / "parkings_aper_leads.csv"
    csv.write_text("nom;siren\nCarrefour;552100554\n", encoding="utf-8")
    return ResumeAper(
        date_run="2026-06-02",
        nb_lignes_brutes=300,
        nb_parkings_aper=42,
        nb_nouveaux=30,
        nb_deja_vus=12,
        nb_top_leads=8,
        cout_l4_eur=0.3142,
        chemin_csv=csv,
        extraits_top=[
            {
                "nom": "Carrefour Lens",
                "siren": "552100554",
                "score": "91",
                "surface": "12000",
                "echeance": "2026-07-01",
                "priorite": "haute",
                "raison": "Hyper > 10 000 m², échéance proche",
            }
        ],
    )


class TestCorps:
    def test_texte_inclut_kpis_et_echeance(self, tmp_path):
        texte = _corps_texte(_resume(tmp_path))
        assert "2026-06-02" in texte
        assert "42" in texte
        assert "Carrefour Lens" in texte
        assert "2026-07-01" in texte
        assert "haute" in texte

    def test_html_inclut_surface_et_priorite(self, tmp_path):
        html = _corps_html(_resume(tmp_path))
        assert "12000 m²" in html
        assert "haute" in html
        assert "552100554" in html


class TestMessage:
    def test_sujet_et_destinataires(self, tmp_path):
        msg = _construire_message(_config(), _resume(tmp_path))
        assert "Parkings loi APER" in msg["Subject"]
        assert "8 top leads" in msg["Subject"]
        assert msg["To"] == "a@test.fr, b@test.fr"

    def test_piece_jointe_csv(self, tmp_path):
        msg = _construire_message(_config(), _resume(tmp_path))
        pieces = [p.get_filename() for p in msg.iter_attachments()]
        assert "parkings_aper_leads.csv" in pieces
