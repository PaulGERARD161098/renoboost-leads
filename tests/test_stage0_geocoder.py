"""Tests du géocodeur BAN et du mode zone='point' par adresse en clair."""

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
from renoboost_leads.stage0_sirene_first.geocoder import (
    AdresseIntrouvableError,
    BANGeocoder,
    GeocoderConfig,
    ResultatGeocodage,
)


def _geocoder(score_min: float = 0.4) -> BANGeocoder:
    return BANGeocoder(
        GeocoderConfig(rate_limiter=RateLimiter(600), score_min=score_min)
    )


def _feature(lon, lat, score, label="Allée de l'Ecopark 59118 Wambrechies"):
    return {
        "features": [
            {
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {"score": score, "label": label},
            }
        ]
    }


# ════════════════════════════════════════════════════════════════
# Géocodeur — succès / échecs
# ════════════════════════════════════════════════════════════════


def test_geocoder_succes(monkeypatch):
    g = _geocoder()
    monkeypatch.setattr(
        BANGeocoder, "_appeler", lambda self, adresse: _feature(3.0473, 50.6758, 0.92)
    )
    res = g.geocoder("Allée de l'Ecopark, Wambrechies")
    assert isinstance(res, ResultatGeocodage)
    # GeoJSON = [lon, lat] → on doit récupérer lat/lon dans le bon ordre
    assert res.latitude == 50.6758
    assert res.longitude == 3.0473
    assert res.score == 0.92


def test_geocoder_aucun_resultat(monkeypatch):
    g = _geocoder()
    monkeypatch.setattr(BANGeocoder, "_appeler", lambda self, adresse: {"features": []})
    with pytest.raises(AdresseIntrouvableError):
        g.geocoder("adresse bidon zzz")


def test_geocoder_score_trop_bas(monkeypatch):
    g = _geocoder(score_min=0.5)
    monkeypatch.setattr(
        BANGeocoder, "_appeler", lambda self, adresse: _feature(3.0, 50.0, 0.2)
    )
    with pytest.raises(AdresseIntrouvableError):
        g.geocoder("rue vague")


def test_geocoder_adresse_vide():
    g = _geocoder()
    with pytest.raises(AdresseIntrouvableError):
        g.geocoder("   ")


def test_geocoder_feature_sans_coordonnees(monkeypatch):
    g = _geocoder()
    monkeypatch.setattr(
        BANGeocoder,
        "_appeler",
        lambda self, adresse: {"features": [{"geometry": {}, "properties": {"score": 0.9}}]},
    )
    with pytest.raises(AdresseIntrouvableError):
        g.geocoder("Allée de l'Ecopark")


# ════════════════════════════════════════════════════════════════
# Extracteur — zone='point' par adresse → géocodage → near_point
# ════════════════════════════════════════════════════════════════


class _FakeClientGeo:
    def __init__(self, entreprises):
        self._entreprises = entreprises
        self.appels_near_point = []

    def decouvrir_near_point(self, **kwargs):
        self.appels_near_point.append(kwargs)
        yield from self._entreprises

    def decouvrir(self, **kwargs):  # pragma: no cover - ne doit pas être appelé
        raise AssertionError("decouvrir (départemental) ne doit pas être appelé")


class _FakeGeocoder:
    def __init__(self, lat, lon):
        self._res = ResultatGeocodage(latitude=lat, longitude=lon, label="L", score=0.9)
        self.appels = []

    def geocoder(self, adresse):
        self.appels.append(adresse)
        return self._res


def _entreprise(siren):
    return {
        "siren": siren,
        "nom_complet": "ACME",
        "siege": {"departement": "59", "libelle_commune": "WAMBRECHIES"},
        "activite_principale": "46.90Z",
        "matching_etablissements": [{"est_siege": True}],
    }


def _config_adresse(adresse="Allée de l'Ecopark, Wambrechies"):
    return CampaignConfig(
        run=RunInfo(client_name="t", description="d", campaign_date="2026-01-01"),
        stages=StagesFlags(enable_stage_1_decouverte=True),
        secteurs=[SecteurCible(type="za", query="parc")],
        zone=Zone(type="point", adresse=adresse, rayon_par_point_km=0.4),
        filtres_entreprise=FiltresEntreprise(),
        volume=Volume(cible=10),
        budget=Budget(max_eur=5.0),
    )


def test_extracteur_adresse_geocode_puis_near_point():
    client = _FakeClientGeo([_entreprise("111111111")])
    geocoder = _FakeGeocoder(50.6758, 3.0473)
    leads = ExtracteurStage0(
        client=client, config=_config_adresse(), geocoder=geocoder
    ).extraire()

    assert geocoder.appels == ["Allée de l'Ecopark, Wambrechies"]
    kwargs = client.appels_near_point[0]
    assert kwargs["latitude"] == 50.6758
    assert kwargs["longitude"] == 3.0473
    assert {lead.siren for lead in leads} == {"111111111"}


def test_extracteur_coords_prioritaires_sur_adresse():
    """Si lat/long ET adresse sont fournis, on n'appelle pas le géocodeur."""
    client = _FakeClientGeo([_entreprise("111111111")])
    geocoder = _FakeGeocoder(0.0, 0.0)
    cfg = CampaignConfig(
        run=RunInfo(client_name="t", description="d", campaign_date="2026-01-01"),
        stages=StagesFlags(enable_stage_1_decouverte=True),
        secteurs=[SecteurCible(type="za", query="parc")],
        zone=Zone(
            type="point",
            latitude=50.6758,
            longitude=3.0473,
            adresse="ignorée",
            rayon_par_point_km=0.4,
        ),
        filtres_entreprise=FiltresEntreprise(),
        volume=Volume(cible=10),
        budget=Budget(max_eur=5.0),
    )
    ExtracteurStage0(client=client, config=cfg, geocoder=geocoder).extraire()
    assert geocoder.appels == []  # coords priment
    assert client.appels_near_point[0]["latitude"] == 50.6758


def test_extracteur_adresse_sans_geocodeur_leve():
    client = _FakeClientGeo([])
    with pytest.raises(ValueError, match="géocodeur"):
        ExtracteurStage0(client=client, config=_config_adresse(), geocoder=None).extraire()
