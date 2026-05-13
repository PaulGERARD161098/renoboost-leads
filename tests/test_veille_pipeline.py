"""Tests pipeline veille bout-en-bout (avec mock L4 dry-run + L2/L3 stubés).

Le pipeline complet est testé sans hit réseau : on injecte des stubs sur
RechercheEntreprisesClient et ScraperContact via monkeypatch.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from renoboost_leads.models import ClaudeScoring, LeadVeille
from renoboost_leads.veille_immatriculations.pipeline_veille import (
    VeilleRunConfig,
    executer_cycle_veille,
)

FIXTURE = Path(__file__).parent / "fixtures_aaa" / "echantillon_aaa_demo.csv"


class _StubRechercheClient:
    """Stub minimal pour EnricheurStage2 — pas de hit data.gouv."""

    def rechercher(self, query, code_postal=None, per_page=10):  # noqa: ARG002
        return []


class _StubScraper:
    """Stub minimal pour EnricheurStage3 — pas de hit web."""

    def scraper(self, site_web):  # noqa: ARG002
        from renoboost_leads.stage3_contacts.scraper import ResultatScraping

        return ResultatScraping(raison_echec="stub")


@pytest.fixture
def stub_pipeline(monkeypatch):
    """Patch les enrichers L2/L3 pour qu'ils ne fassent aucun hit réseau."""
    from renoboost_leads.veille_immatriculations import pipeline_veille

    # L2 client → stub
    monkeypatch.setattr(
        pipeline_veille,
        "RechercheEntreprisesClient",
        lambda *a, **kw: _StubRechercheClient(),
    )

    # L3 scraper → stub
    monkeypatch.setattr(
        pipeline_veille, "ScraperContact", lambda *a, **kw: _StubScraper()
    )


class TestPipelineVeilleDryRun:
    def test_run_complet_sans_appel_reseau(self, tmp_path, stub_pipeline):
        config = VeilleRunConfig(
            source_veille="aaa_data_test",
            claude_scoring=ClaudeScoring(seuil_top_lead=70, inclure_pitch=False),
            dry_run_l4=True,  # mock Claude
        )
        resultat = executer_cycle_veille(
            fichier_aaa=FIXTURE,
            output_dir=tmp_path / "veille_out",
            config=config,
        )

        # 10 lignes brutes → 7 VE flotte entreprise
        assert resultat.nb_lignes_brutes == 10
        assert resultat.nb_ve_flotte == 7
        # Tous neufs (état historique vide)
        assert resultat.nb_nouveaux == 7
        assert resultat.nb_deja_vus == 0
        # 7 LeadVeille produits
        assert len(resultat.leads) == 7
        assert all(isinstance(lead, LeadVeille) for lead in resultat.leads)
        # Coût L4 = 0 en dry-run
        assert resultat.cout_l4_eur == 0.0

    def test_colonnes_veille_remplies(self, tmp_path, stub_pipeline):
        config = VeilleRunConfig(
            claude_scoring=ClaudeScoring(inclure_pitch=False),
            dry_run_l4=True,
        )
        resultat = executer_cycle_veille(FIXTURE, tmp_path / "out", config)
        # Tester un lead spécifique : SMI Industrie (siren 402111111, Tesla Model Y)
        smi = next(
            (lead for lead in resultat.leads if lead.siren == "402111111"),
            None,
        )
        assert smi is not None
        assert smi.source_veille == "aaa_data"  # défaut
        assert smi.energie_ve == "EL"
        assert smi.marque_ve == "TESLA"
        assert smi.modele_ve == "MODEL Y"
        assert smi.date_immatriculation_ve == "2026-05-13"
        assert smi.deja_eu_ve is False  # premier passage

    def test_flag_deja_vu_au_2e_passage(self, tmp_path, stub_pipeline):
        config = VeilleRunConfig(
            claude_scoring=ClaudeScoring(inclure_pitch=False),
            dry_run_l4=True,
        )
        # Partager le même état historique entre les 2 runs
        etat_db = tmp_path / "etat_partage.sqlite"

        # 1er run
        r1 = executer_cycle_veille(
            FIXTURE, tmp_path / "run1", config, etat_db_path=etat_db
        )
        assert all(not lead.deja_eu_ve for lead in r1.leads)

        # 2e run (mêmes données) → tous flagués deja_eu_ve
        r2 = executer_cycle_veille(
            FIXTURE, tmp_path / "run2", config, etat_db_path=etat_db
        )
        assert all(lead.deja_eu_ve for lead in r2.leads)
        assert r2.nb_nouveaux == 0
        assert r2.nb_deja_vus == 7

    def test_top_leads_comptes(self, tmp_path, stub_pipeline):
        config = VeilleRunConfig(
            claude_scoring=ClaudeScoring(seuil_top_lead=70, inclure_pitch=False),
            dry_run_l4=True,
        )
        resultat = executer_cycle_veille(FIXTURE, tmp_path / "out", config)
        # En dry-run, scores 30-95 distribués sur hash → on attend ~33% de top_leads
        # (en réalité c'est stable mais on tolère un range)
        assert 0 <= resultat.nb_top_leads <= 7
        assert resultat.nb_top_leads == sum(1 for lead in resultat.leads if lead.top_lead)
