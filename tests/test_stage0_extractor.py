"""Tests de l'extracteur stage0 SIRENE-first."""

from __future__ import annotations

from typing import Any

import pytest

from renoboost_leads.models import (
    Budget,
    CampaignConfig,
    FiltresEntreprise,
    RunInfo,
    SecteurCible,
    StagesFlags,
    Volume,
    Zone,
)
from renoboost_leads.stage0_sirene_first.extractor import (
    ExtracteurStage0,
    tranches_pour_effectif,
)


def _config(
    *,
    departements: list[str] | None = None,
    zone_type: str = "departement",
    naf_inclus: list[str] | None = None,
    effectif_min: int | None = None,
    effectif_max: int | None = None,
    ca_min: int | None = None,
    ca_max: int | None = None,
    categorie: list[str] | None = None,
    volume_cible: int = 10,
) -> CampaignConfig:
    return CampaignConfig(
        run=RunInfo(client_name="t", description="d", campaign_date="2026-01-01"),
        stages=StagesFlags(),
        secteurs=[SecteurCible(type="t", query="q")],
        zone=Zone(type=zone_type, codes=departements or ["59"]),  # type: ignore[arg-type]
        filtres_entreprise=FiltresEntreprise(
            naf_inclus=naf_inclus or [],
            effectif_min=effectif_min,
            effectif_max=effectif_max,
            ca_min=ca_min,
            ca_max=ca_max,
            categorie_entreprise_inclus=categorie or [],
        ),
        volume=Volume(cible=volume_cible),
        budget=Budget(max_eur=10),
    )


class _FakeClient:
    """Simule RechercheEntreprisesClient.decouvrir : renvoie une liste fixe."""

    def __init__(self, entreprises: list[dict[str, Any]]):
        self.entreprises = entreprises
        self.captured: dict[str, Any] = {}

    def decouvrir(self, **kwargs):
        self.captured = kwargs
        yield from self.entreprises


def _entreprise(siren: str, nom: str = "TEST SAS") -> dict[str, Any]:
    return {
        "siren": siren,
        "nom_complet": nom,
        "etat_administratif": "A",
        "tranche_effectif_salarie": "12",
        "siege": {"siret": f"{siren}00015", "code_postal": "59000", "departement": "59"},
        "finances": {},
        "dirigeants": [],
    }


class TestTranchesPourEffectif:
    def test_vide_si_pas_de_borne(self):
        assert tranches_pour_effectif(None, None) == []

    def test_5_50_couvre_02_a_21(self):
        # tranches qui chevauchent [5,50] :
        # 02 (3-5), 03 (6-9), 11 (10-19), 12 (20-49), 21 (50-99) car borne 50 incluse
        codes = tranches_pour_effectif(5, 50)
        assert codes == ["02", "03", "11", "12", "21"]

    def test_min_seul_inclut_tout_au_dessus(self):
        # min=20 → tranches couvrant 20+
        codes = tranches_pour_effectif(20, None)
        assert "12" in codes  # 20-49 chevauche
        assert "53" in codes  # 10000+ chevauche (tmax=999_999)
        assert "11" not in codes  # 10-19 strictement en dessous

    def test_max_seul_inclut_tout_en_dessous(self):
        codes = tranches_pour_effectif(None, 9)
        assert "00" in codes  # 0
        assert "01" in codes  # 1-2
        assert "02" in codes  # 3-5
        assert "03" in codes  # 6-9
        assert "11" not in codes  # 10-19 hors


class TestExtraireFiltres:
    def test_filtres_passes_au_client(self):
        client = _FakeClient([])
        cfg = _config(
            departements=["59", "62"],
            naf_inclus=["49.41A", "77.11A"],
            effectif_min=5,
            effectif_max=50,
            ca_min=500_000,
            ca_max=5_000_000,
            categorie=["PME"],
        )
        ExtracteurStage0(client, cfg).extraire()  # type: ignore[arg-type]

        assert client.captured["departements"] == ["59", "62"]
        assert client.captured["activite_principale"] == ["49.41A", "77.11A"]
        assert client.captured["tranche_effectif_salarie"] == ["02", "03", "11", "12", "21"]
        assert client.captured["ca_min"] == 500_000
        assert client.captured["ca_max"] == 5_000_000
        assert client.captured["categorie_entreprise"] == ["PME"]
        assert client.captured["etat_administratif"] == "A"
        assert client.captured["siege_only"] is True

    def test_pas_de_naf_passe_none(self):
        client = _FakeClient([])
        cfg = _config(naf_inclus=[])
        ExtracteurStage0(client, cfg).extraire()  # type: ignore[arg-type]
        assert client.captured["activite_principale"] is None

    def test_tranche_effectif_inclus_prioritaire(self):
        # Si l'utilisateur a posé les codes INSEE bruts, on les passe tels quels
        client = _FakeClient([])
        cfg = CampaignConfig(
            run=RunInfo(client_name="t", description="d", campaign_date="2026-01-01"),
            stages=StagesFlags(),
            secteurs=[SecteurCible(type="t", query="q")],
            zone=Zone(type="departement", codes=["59"]),
            filtres_entreprise=FiltresEntreprise(
                tranche_effectif_inclus=["03", "11"],
                effectif_min=5,
                effectif_max=50,
            ),
            volume=Volume(cible=10),
            budget=Budget(max_eur=10),
        )
        ExtracteurStage0(client, cfg).extraire()  # type: ignore[arg-type]
        assert client.captured["tranche_effectif_salarie"] == ["03", "11"]


class TestExtraireResultats:
    def test_plafonne_au_volume_cible(self):
        client = _FakeClient([_entreprise(f"{i:09d}") for i in range(100)])
        cfg = _config(volume_cible=5)
        leads = ExtracteurStage0(client, cfg).extraire()  # type: ignore[arg-type]
        assert len(leads) == 5

    def test_dedup_par_siren(self):
        client = _FakeClient([_entreprise("111"), _entreprise("111"), _entreprise("222")])
        cfg = _config(volume_cible=10)
        leads = ExtracteurStage0(client, cfg).extraire()  # type: ignore[arg-type]
        assert [lead.siren for lead in leads] == ["111", "222"]

    def test_max_results_marge_par_rapport_a_cible(self):
        client = _FakeClient([])
        cfg = _config(volume_cible=10)
        ExtracteurStage0(client, cfg).extraire()  # type: ignore[arg-type]
        # Marge : max(cible*2, cible+50) → 60 pour cible=10
        assert client.captured["max_results"] >= 50

    def test_entreprise_sans_siren_ignoree(self):
        client = _FakeClient([
            {"nom_complet": "SANS SIREN", "siege": {}},  # mapping échoue
            _entreprise("222"),
        ])
        cfg = _config(volume_cible=10)
        leads = ExtracteurStage0(client, cfg).extraire()  # type: ignore[arg-type]
        assert [lead.siren for lead in leads] == ["222"]


class TestZoneSupport:
    def test_zone_non_departement_leve(self):
        client = _FakeClient([])
        cfg = _config(zone_type="ville", departements=["34000"])
        with pytest.raises(NotImplementedError, match="ville"):
            ExtracteurStage0(client, cfg).extraire()  # type: ignore[arg-type]


class TestFiltresEntreprise:
    def test_naf_exclus_flague_hors_filtre(self):
        # Une SCI (NAF 68.20B) doit être conservée mais flaguée hors-filtre,
        # pas droppée (pattern flag-not-drop). Sans ce câblage, naf_exclus
        # serait sans effet en mode SIRENE-first.
        sci = _entreprise("111")
        sci["siege"]["code_postal"] = "59118"
        sci["activite_principale"] = "68.20B"
        pme = _entreprise("222")
        pme["activite_principale"] = "46.90Z"
        client = _FakeClient([sci, pme])
        cfg = _config(volume_cible=10)
        cfg.filtres_entreprise.naf_exclus = ["68.20"]

        leads = ExtracteurStage0(client, cfg).extraire()  # type: ignore[arg-type]

        par_siren = {lead.siren: lead for lead in leads}
        assert len(leads) == 2  # aucun drop
        assert par_siren["111"].hors_filtre_entreprise is True
        assert "68.20" in (par_siren["111"].raison_hors_filtre or "")
        assert par_siren["222"].hors_filtre_entreprise is False
