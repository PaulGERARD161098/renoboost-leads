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
    def __init__(self, near_point_candidats=None):
        self._near = near_point_candidats or []

    def rechercher(self, query, code_postal=None, per_page=10):  # noqa: ARG002
        return []

    def decouvrir_near_point(self, latitude, longitude, radius_km, **kwargs):  # noqa: ARG002
        yield from self._near


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

    def test_petit_parking_hors_obligation(self, tmp_path, stub_pipeline):
        # En abaissant le seuil, les petits parkings (< 1 500 m²) entrent dans le
        # run mais sont marqués hors obligation (pas d'échéance, priorité dédiée).
        from renoboost_leads.parkings_aper.models import AperConfig

        config = AperRunConfig(
            aper_config=AperConfig(surface_min_m2=300.0),
            claude_scoring=ClaudeScoring(inclure_pitch=False),
            dry_run_l4=True,
        )
        res = executer_cycle_aper(FIXTURE, tmp_path / "out", config)
        assert res.nb_parkings_aper == 10  # tous, y compris 850 et 420 m²

        petit = next(la for la in res.leads if la.surface_parking_m2 == 420.0)
        assert petit.echeance_aper is None
        assert petit.priorite_aper == "hors_obligation"

        gros = next(la for la in res.leads if la.surface_parking_m2 == 31000.0)
        assert gros.priorite_aper == "haute"

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

    def test_contexte_pour_surface_obligation_vs_flotte(self):
        from renoboost_leads.parkings_aper.pipeline_aper import (
            CONTEXTE_APER_DEFAUT,
            CONTEXTE_PETIT_PARKING_DEFAUT,
            _contexte_pour_surface,
        )

        assert _contexte_pour_surface(5000) == CONTEXTE_APER_DEFAUT
        assert _contexte_pour_surface(1500) == CONTEXTE_APER_DEFAUT  # seuil inclus
        assert _contexte_pour_surface(400) == CONTEXTE_PETIT_PARKING_DEFAUT

    def test_resolver_contexte_par_place_id(self):
        from renoboost_leads.parkings_aper.adaptateur_lead_l2 import (
            ligne_parking_vers_lead_stage1,
        )
        from renoboost_leads.parkings_aper.models import LigneParking
        from renoboost_leads.parkings_aper.pipeline_aper import (
            CONTEXTE_APER_DEFAUT,
            CONTEXTE_PETIT_PARKING_DEFAUT,
            _construire_resolver_contexte,
        )

        lignes = [
            LigneParking(identifiant="big", surface_m2=5000),
            LigneParking(identifiant="small", surface_m2=400),
        ]
        leads_l1 = [ligne_parking_vers_lead_stage1(lg) for lg in lignes]
        resolver = _construire_resolver_contexte(leads_l1, lignes)

        assert resolver(leads_l1[0]) == CONTEXTE_APER_DEFAUT
        assert resolver(leads_l1[1]) == CONTEXTE_PETIT_PARKING_DEFAUT


class TestL35Integration:
    """L3.5 Dropcontact câblé au pipeline APER (opt-in)."""

    def test_l35_skippe_par_defaut(self, tmp_path, stub_pipeline):
        config = AperRunConfig(
            claude_scoring=ClaudeScoring(inclure_pitch=False), dry_run_l4=True
        )
        res = executer_cycle_aper(FIXTURE, tmp_path / "out", config)
        assert res.cout_l35_eur == 0.0
        assert res.nb_emails_l35 == 0
        assert all(la.email_dropcontact is None for la in res.leads)

    def test_l35_execute_si_active(self, tmp_path, stub_pipeline, monkeypatch):
        from renoboost_leads.models import LeadStage35
        from renoboost_leads.parkings_aper import pipeline_aper

        class _StubEnr35:
            def __init__(self, *a, **kw):
                self.cout_total_eur = 0.40

            def enrichir(self, leads):
                return [
                    LeadStage35(**lead.model_dump(), email_dropcontact="dir@x.fr")
                    for lead in leads
                ]

        monkeypatch.setattr(pipeline_aper, "EnricheurStage35", _StubEnr35)
        config = AperRunConfig(
            claude_scoring=ClaudeScoring(inclure_pitch=False),
            dry_run_l4=True,
            enrichir_l3_5=True,
        )
        res = executer_cycle_aper(FIXTURE, tmp_path / "out", config)
        assert res.cout_l35_eur == 0.40
        assert res.nb_emails_l35 == 8
        assert all(la.email_dropcontact == "dir@x.fr" for la in res.leads)


class TestBudgetEtDegradation:
    """Budget L4 indépendant de L3.5 + flag anti-dégradation silencieuse."""

    def test_budget_l4_independant_par_defaut(self):
        cfg = AperRunConfig()
        # L4 (Claude, quasi-gratuit) a sa propre enveloppe, distincte de L3.5.
        assert cfg.budget_l4_eur == 5.0
        assert cfg.budget_eur == 5.0

    def test_pas_de_degradation_si_tout_score(self, tmp_path, stub_pipeline):
        config = AperRunConfig(
            claude_scoring=ClaudeScoring(inclure_pitch=False), dry_run_l4=True
        )
        res = executer_cycle_aper(FIXTURE, tmp_path / "out", config)
        assert res.nb_scores_ko == 0
        assert res.raison_degradation is None

    def test_degradation_flaggee_si_scoring_incomplet(
        self, tmp_path, stub_pipeline, monkeypatch
    ):
        from renoboost_leads.models import LeadStage4
        from renoboost_leads.parkings_aper import pipeline_aper

        class _StubEnr4Affame:
            """Simule un L4 affamé : aucun lead scoré (budget épuisé)."""

            def __init__(self, *a, **kw):
                self.cout_total_eur = 0.0

            def enrichir(self, leads):
                return [
                    LeadStage4(
                        **lead.model_dump(),
                        score_interet=None,
                        top_lead=False,
                        scoring_erreur="budget_exhausted",
                    )
                    for lead in leads
                ]

        monkeypatch.setattr(pipeline_aper, "EnricheurStage4", _StubEnr4Affame)
        config = AperRunConfig(
            claude_scoring=ClaudeScoring(inclure_pitch=False), dry_run_l4=True
        )
        res = executer_cycle_aper(FIXTURE, tmp_path / "out", config)
        assert res.nb_scores_ko == res.nb_parkings_aper
        assert res.nb_top_leads == 0
        assert res.raison_degradation is not None
        assert "non scorés" in res.raison_degradation


class TestPhaseCDIntegration:
    """Phase C (géoloc → SIREN) + Phase D (email post-run) câblées au pipeline."""

    def _csv_sans_enseigne(self, tmp_path: Path) -> Path:
        # Parking sans NOM ni SIREN, mais avec coordonnées → cible Phase C.
        csv = tmp_path / "inv.csv"
        csv.write_text(
            "IDENTIFIANT;NOM;SIREN;SURFACE_M2;LATITUDE;LONGITUDE\n"
            "osm-9001;;;14500;50.4281;2.8319\n",
            encoding="utf-8",
        )
        return csv

    def test_phase_c_resout_par_geoloc(self, tmp_path, monkeypatch):
        from renoboost_leads.parkings_aper import pipeline_aper

        candidat = {
            "siren": "552100554", "nom_complet": "Foncière Parc SA",
            "tranche_effectif_salarie": "32",
        }
        monkeypatch.setattr(
            pipeline_aper, "RechercheEntreprisesClient",
            lambda *a, **kw: _StubRechercheClient(near_point_candidats=[candidat]),
        )
        monkeypatch.setattr(
            pipeline_aper, "ScraperContact", lambda *a, **kw: _StubScraper()
        )
        config = AperRunConfig(
            claude_scoring=ClaudeScoring(inclure_pitch=False), dry_run_l4=True
        )
        res = executer_cycle_aper(
            self._csv_sans_enseigne(tmp_path), tmp_path / "out", config
        )
        assert res.nb_resolus_geo == 1

    def test_phase_c_desactivable(self, tmp_path, stub_pipeline):
        config = AperRunConfig(
            claude_scoring=ClaudeScoring(inclure_pitch=False),
            dry_run_l4=True,
            resoudre_geo=False,
        )
        res = executer_cycle_aper(
            self._csv_sans_enseigne(tmp_path), tmp_path / "out", config
        )
        assert res.nb_resolus_geo == 0

    def test_phase_d_envoie_si_smtp(self, tmp_path, stub_pipeline, monkeypatch):
        from renoboost_leads.parkings_aper import pipeline_aper
        from renoboost_leads.veille_immatriculations.mailer import ConfigSMTP

        envois: list = []
        monkeypatch.setattr(
            pipeline_aper, "envoyer_resume_aper",
            lambda cfg, resume: envois.append(resume),
        )
        smtp = ConfigSMTP(
            host="smtp.test", port=587, user="u@test.fr",
            password="x",  # noqa: S106 — placeholder de test
            expediteur="from@test.fr", destinataires=["a@test.fr"],
        )
        config = AperRunConfig(
            claude_scoring=ClaudeScoring(inclure_pitch=False),
            dry_run_l4=True,
            smtp_config=smtp,
        )
        executer_cycle_aper(FIXTURE, tmp_path / "out", config)
        assert len(envois) == 1
        assert envois[0].nb_parkings_aper == 8
