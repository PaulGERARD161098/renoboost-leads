"""Tests du mode découverte géographique (zone type='point', near_point).

Couvre :
- la validation du modèle Zone en mode point,
- le filtrage « siège dans la zone » du client (helper _siege_dans_zone),
- la construction des params near_point,
- le branchement de l'extracteur étage 0 sur decouvrir_near_point.
"""

from __future__ import annotations

import pytest

from renoboost_leads.common.rate_limiter import RateLimiter
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
from renoboost_leads.stage0_sirene_first.extractor import ExtracteurStage0
from renoboost_leads.stage2_entreprises.recherche_client import (
    NEAR_POINT_URL,
    RechercheClientConfig,
    RechercheEntreprisesClient,
)

# ════════════════════════════════════════════════════════════════
# Modèle Zone — mode point
# ════════════════════════════════════════════════════════════════


def test_zone_point_valide():
    z = Zone(type="point", latitude=50.6758, longitude=3.0473, rayon_par_point_km=0.4)
    assert z.type == "point"
    assert z.codes == []  # codes optionnel en mode point


def test_zone_point_exige_coordonnees():
    with pytest.raises(ValueError):
        Zone(type="point", rayon_par_point_km=0.4)


def test_zone_departement_exige_codes():
    with pytest.raises(ValueError):
        Zone(type="departement")


def test_zone_departement_inchangee():
    z = Zone(type="departement", codes=["59"])
    assert z.codes == ["59"]
    assert z.latitude is None


# ════════════════════════════════════════════════════════════════
# Client — filtrage siège & params near_point
# ════════════════════════════════════════════════════════════════


def test_siege_dans_zone_vrai():
    ent = {
        "siren": "1",
        "matching_etablissements": [
            {"est_siege": False},
            {"est_siege": True},
        ],
    }
    assert RechercheEntreprisesClient._siege_dans_zone(ent) is True


def test_siege_dans_zone_faux():
    # Antenne de groupe : établissement dans le rayon mais ce n'est pas le siège.
    ent = {
        "siren": "2",
        "matching_etablissements": [{"est_siege": False}],
    }
    assert RechercheEntreprisesClient._siege_dans_zone(ent) is False


def test_siege_dans_zone_aucun_etablissement():
    assert RechercheEntreprisesClient._siege_dans_zone({"siren": "3"}) is False


def _client():
    return RechercheEntreprisesClient(
        RechercheClientConfig(rate_limiter=RateLimiter(600))
    )


def test_decouvrir_near_point_params_et_filtrage(monkeypatch):
    """Vérifie l'URL, les params lat/long/radius+filtres et le filtrage siège."""
    appels = []

    page = {
        "results": [
            {
                "siren": "111111111",
                "nom_complet": "SIEGE DANS ZONE",
                "matching_etablissements": [{"est_siege": True}],
            },
            {
                "siren": "222222222",
                "nom_complet": "ANTENNE GROUPE",
                "matching_etablissements": [{"est_siege": False}],
            },
        ],
        "total_pages": 1,
        "total_results": 2,
    }

    def fake_search_page(self, params, url=None):
        appels.append((url, params))
        return page

    monkeypatch.setattr(
        RechercheEntreprisesClient, "_search_page", fake_search_page, raising=True
    )

    client = _client()
    out = list(
        client.decouvrir_near_point(
            latitude=50.6758,
            longitude=3.0473,
            radius_km=0.4,
            activite_principale=["46.90Z"],
            ca_min=100000,
            siege_only=True,
            max_results=50,
        )
    )

    # Seul le siège dans la zone est conservé
    assert [e["siren"] for e in out] == ["111111111"]
    # URL near_point + params géo et filtres bien transmis
    url, params = appels[0]
    assert url == NEAR_POINT_URL
    assert params["lat"] == 50.6758
    assert params["long"] == 3.0473
    assert params["radius"] == 0.4
    assert params["activite_principale"] == "46.90Z"
    assert params["ca_min"] == 100000


def test_decouvrir_near_point_sans_filtre_siege(monkeypatch):
    page = {
        "results": [
            {"siren": "1", "nom_complet": "A", "matching_etablissements": [{"est_siege": False}]},
        ],
        "total_pages": 1,
        "total_results": 1,
    }
    monkeypatch.setattr(
        RechercheEntreprisesClient,
        "_search_page",
        lambda self, params, url=None: page,
        raising=True,
    )
    client = _client()
    out = list(
        client.decouvrir_near_point(
            latitude=1.0, longitude=2.0, radius_km=1.0, siege_only=False
        )
    )
    assert [e["siren"] for e in out] == ["1"]


# ════════════════════════════════════════════════════════════════
# Extracteur — branchement zone point → decouvrir_near_point
# ════════════════════════════════════════════════════════════════


class _FakeClientGeo:
    """Capture l'appel near_point et renvoie une séquence figée."""

    def __init__(self, entreprises):
        self._entreprises = entreprises
        self.appels_near_point = []
        self.appels_decouvrir = []

    def decouvrir_near_point(self, **kwargs):
        self.appels_near_point.append(kwargs)
        yield from self._entreprises

    def decouvrir(self, **kwargs):
        self.appels_decouvrir.append(kwargs)
        yield from self._entreprises


def _config_point():
    return CampaignConfig(
        run=RunInfo(client_name="t", description="d", campaign_date="2026-01-01"),
        stages=StagesFlags(enable_stage_1_decouverte=True),
        secteurs=[SecteurCible(type="za", query="parc d'activités")],
        zone=Zone(type="point", latitude=50.6758, longitude=3.0473, rayon_par_point_km=0.4),
        filtres_entreprise=FiltresEntreprise(),
        volume=Volume(cible=10),
        budget=Budget(max_eur=5.0),
    )


def _entreprise(siren, nom="ACME"):
    return {
        "siren": siren,
        "nom_complet": nom,
        "siege": {"departement": "59", "libelle_commune": "WAMBRECHIES"},
        "activite_principale": "46.90Z",
        "matching_etablissements": [{"est_siege": True}],
    }


def test_extracteur_point_utilise_near_point():
    client = _FakeClientGeo([_entreprise("111111111"), _entreprise("222222222", "B")])
    leads = ExtracteurStage0(client=client, config=_config_point()).extraire()

    # On est bien passé par near_point, pas par decouvrir (départemental)
    assert len(client.appels_near_point) == 1
    assert client.appels_decouvrir == []

    kwargs = client.appels_near_point[0]
    assert kwargs["latitude"] == 50.6758
    assert kwargs["longitude"] == 3.0473
    assert kwargs["radius_km"] == 0.4
    assert kwargs["siege_only"] is True

    assert {lead.siren for lead in leads} == {"111111111", "222222222"}
    assert all(lead.ville == "WAMBRECHIES" for lead in leads)


def test_extracteur_point_dedup_par_siren():
    client = _FakeClientGeo([_entreprise("111111111"), _entreprise("111111111", "dup")])
    leads = ExtracteurStage0(client=client, config=_config_point()).extraire()
    assert len(leads) == 1
