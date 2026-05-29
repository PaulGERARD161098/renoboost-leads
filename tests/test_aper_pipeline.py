"""Tests pipeline parkings APER bout-en-bout (L2/L3 stubés, L4 dry-run)."""

from __future__ import annotations

from pathlib import Path

import pytest

from renoboost_leads.models import ClaudeScoring, LeadAper
from renoboost_leads.parkings_aper.pipeline_aper import (
    AperRunConfig,
    executer_cycle_aper,
)

FIXTURE = Path(__file__).parent / "fixtures_parkings" / "echantillon_parkings_demo.csv"


class _StubRechercheClient:
    def rechercher(self, query, code_postal=None, per_page=10):  # noqa: ARG002
        return []


class _StubScraper:
    def scraper(self, site_web):  # noqa: ARG002
        from renoboost_leads.stage3_contacts.scraper import ResultatScraping

        return ResultatScraping(raison_echec="stub")


@pytest.fixture
def stub_pipeline(monkeypatch):
    from renoboost_leads.parkings_aper import pipeline_aper

    monkeypatch.setattr(
        pipeline_aper, "RechercheEntreprisesClient",
        lambda *a, **kw: _StubRechercheClient(),
    )
    monkeypatch.setattr(
        pipeline_aper, "ScraperContact", lambda *a, **kw: _StubScraper()
    )


class TestPipelineAperDryRun:
    def test_run_complet_sans_reseau(self, tmp_path, stub_pipeline):
        config = AperRunConfig(
            claude_scoring=ClaudeScoring(seuil_top_lead=70, inclure_pitch=False),
            dry_run_l4=True,
        )
        res = executer_cycle_aper(FIXTURE, tmp_path / "out", config)
        assert res.nb_lignes_brutes == 10
        assert res.nb_parkings_aper == 8
        assert res.nb_nouveaux == 8
        assert res.nb_deja_vus == 0
        assert len(res.leads) == 8
        assert all(isinstance(la, LeadAper) for la in res.leads)
        assert res.cout_l4_eur == 0.0

    def test_colonnes_aper_remplies(self, tmp_path, stub_pipeline):
        config = AperRunConfig(
            claude_scoring=ClaudeScoring(inclure_pitch=False), dry_run_l4=True
        )
        res = executer_cycle_aper(FIXTURE, tmp_path / "out", config)
        gros = next(la for la in res.leads if la.surface_parking_m2 == 31000.0)
        assert gros.echeance_aper == "2026-07-01"
        assert gros.priorite_aper == "haute"
        assert gros.surface_ombrable_m2 == 15500.0
        assert gros.source_aper == "aper_osm"

        moyen = next(la for la in res.leads if la.surface_parking_m2 == 5600.0)
        assert moyen.echeance_aper == "2028-07-01"
        assert moyen.priorite_aper == "standard"

    def test_csv_ecrit(self, tmp_path, stub_pipeline):
        config = AperRunConfig(
            claude_scoring=ClaudeScoring(inclure_pitch=False), dry_run_l4=True
        )
        out = tmp_path / "out"
        executer_cycle_aper(FIXTURE, out, config)
        assert (out / "parkings_aper_leads.csv").exists()

    def test_dedup_2e_passage(self, tmp_path, stub_pipeline):
        config = AperRunConfig(
            claude_scoring=ClaudeScoring(inclure_pitch=False), dry_run_l4=True
        )
        etat = tmp_path / "etat.sqlite"
        r1 = executer_cycle_aper(FIXTURE, tmp_path / "r1", config, etat_db_path=etat)
        assert all(not la.deja_vu_parking for la in r1.leads)
        r2 = executer_cycle_aper(FIXTURE, tmp_path / "r2", config, etat_db_path=etat)
        assert all(la.deja_vu_parking for la in r2.leads)
        assert r2.nb_nouveaux == 0
        assert r2.nb_deja_vus == 8

    def test_contexte_aper_injecte_si_absent(self):
        from renoboost_leads.parkings_aper.pipeline_aper import (
            CONTEXTE_APER_DEFAUT,
            _claude_scoring_avec_contexte,
        )

        base = ClaudeScoring()
        assert base.contexte_client is None
        enrichi = _claude_scoring_avec_contexte(base)
        assert enrichi.contexte_client == CONTEXTE_APER_DEFAUT

    def test_contexte_client_existant_preserve(self):
        from renoboost_leads.parkings_aper.pipeline_aper import (
            _claude_scoring_avec_contexte,
        )

        base = ClaudeScoring(contexte_client="custom")
        assert _claude_scoring_avec_contexte(base).contexte_client == "custom"
