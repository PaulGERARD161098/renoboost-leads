"""Tests de l'export CSV exportable (commande CLI `export` + helper exporter)."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from renoboost_leads.cli import cli
from renoboost_leads.exporter import (
    COLONNES_EXPORT_CRM,
    export_csv_crm,
    export_stage3_5_csv,
    export_stage4_csv,
    lire_stage3_5_csv,
)
from renoboost_leads.models import LeadStage4, LeadStage35


def _lead_l4(
    place_id: str = "p1",
    nom: str = "Acme",
    email_dc: str | None = "paul@acme.fr",
    score: int | None = 85,
    top: bool = True,
) -> LeadStage4:
    return LeadStage4(
        place_id=place_id,
        extraction_date=datetime.now(timezone.utc),
        nom=nom,
        siren="123456789",
        ville="Paris",
        email_dropcontact=email_dc,
        qualification_email_dropcontact="correct" if email_dc else None,
        enrichi_dropcontact=email_dc is not None,
        score_interet=score,
        top_lead=top,
    )


class TestExportCsvCrm:
    def test_genere_csv_avec_colonnes_attendues(self, tmp_path: Path):
        leads = [_lead_l4("p1"), _lead_l4("p2", email_dc=None, top=False)]
        out = export_csv_crm(leads, tmp_path / "export.csv")

        with out.open("r", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        assert reader.fieldnames == COLONNES_EXPORT_CRM
        assert len(rows) == 2
        assert rows[0]["email_dropcontact"] == "paul@acme.fr"
        assert rows[0]["top_lead"] == "VRAI"

    def test_l3_5_round_trip_via_csv(self, tmp_path: Path):
        l35 = LeadStage35(
            place_id="p1",
            extraction_date=datetime.now(timezone.utc),
            nom="Acme",
            email_dropcontact="x@y.fr",
            telephone_direct_dropcontact="+33100000000",
            enrichi_dropcontact=True,
            cout_enrichissement_eur=0.5,
        )
        p = export_stage3_5_csv([l35], tmp_path / "l35.csv")
        relus = lire_stage3_5_csv(p)
        assert len(relus) == 1
        assert relus[0].email_dropcontact == "x@y.fr"
        assert relus[0].telephone_direct_dropcontact == "+33100000000"
        assert relus[0].enrichi_dropcontact is True
        assert relus[0].cout_enrichissement_eur == pytest.approx(0.5)


class TestExportCommand:
    def _setup_session(self, tmp_path: Path) -> Path:
        session_dir = tmp_path / "data" / "output" / "2026-05-14_test"
        session_dir.mkdir(parents=True)
        # Génère un CSV L4 minimal
        leads = [
            _lead_l4("p1", top=True),
            _lead_l4("p2", email_dc=None, top=False),
            _lead_l4("p3", email_dc="alice@x.fr", top=True),
        ]
        export_stage4_csv(leads, session_dir / "etage4_prospection.csv")
        return session_dir

    def test_export_auto_choisit_l4(self, tmp_path: Path, monkeypatch):
        session = self._setup_session(tmp_path)
        # Override PROJECT_ROOT pour pointer sur tmp_path
        monkeypatch.setattr("renoboost_leads.cli.PROJECT_ROOT", tmp_path)

        runner = CliRunner()
        out_csv = session / "leads_exportables.csv"
        result = runner.invoke(cli, ["export", "--session-id", "2026-05-14_test"])
        assert result.exit_code == 0, result.output
        assert out_csv.exists()
        with out_csv.open("r", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 3

    def test_export_top_only_filtre(self, tmp_path: Path, monkeypatch):
        session = self._setup_session(tmp_path)
        monkeypatch.setattr("renoboost_leads.cli.PROJECT_ROOT", tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            cli, ["export", "--session-id", "2026-05-14_test", "--top-only"]
        )
        assert result.exit_code == 0, result.output
        out_csv = session / "leads_exportables_top.csv"
        assert out_csv.exists()
        with out_csv.open("r", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        # 2 leads top sur 3
        assert len(rows) == 2

    def test_export_avec_email_uniquement(self, tmp_path: Path, monkeypatch):
        session = self._setup_session(tmp_path)
        monkeypatch.setattr("renoboost_leads.cli.PROJECT_ROOT", tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            cli, ["export", "--session-id", "2026-05-14_test", "--avec-email-uniquement"]
        )
        assert result.exit_code == 0, result.output
        out_csv = session / "leads_exportables_avec_email.csv"
        with out_csv.open("r", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        # 2 leads ont un email dropcontact (p1 et p3)
        assert len(rows) == 2

    def test_export_session_inexistante_erreur(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("renoboost_leads.cli.PROJECT_ROOT", tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["export", "--session-id", "n-existe-pas"])
        assert result.exit_code == 2
        assert "introuvable" in result.output.lower()
