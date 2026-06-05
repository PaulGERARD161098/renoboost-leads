"""Tests du booster Google Solar API (sans réseau) + override exploitable."""

from __future__ import annotations

from renoboost_leads.potentiel.analyse import analyser_potentiels
from renoboost_leads.potentiel.solar_api import surfaces_solar_api

_LAT, _LON = 50.6292, 3.0573


def _reponse(roof, array):
    sp = {}
    if roof is not None:
        sp["wholeRoofStats"] = {"areaMeters2": roof}
    if array is not None:
        sp["maxArrayAreaMeters2"] = array
    return {"solarPotential": sp}


class TestSolarApi:
    def test_renvoie_toiture_et_exploitable(self):
        s = surfaces_solar_api(
            _LAT, _LON, api_key="k", fetch=lambda *a: _reponse(2000, 1400)
        )
        assert s == (2000.0, 1400.0)

    def test_sans_cle_renvoie_none(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_SOLAR_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
        assert surfaces_solar_api(_LAT, _LON) is None

    def test_erreur_reseau_renvoie_none(self):
        def boom(*a):
            raise RuntimeError("hors couverture")

        assert surfaces_solar_api(_LAT, _LON, api_key="k", fetch=boom) is None

    def test_reponse_vide_renvoie_none(self):
        s = surfaces_solar_api(_LAT, _LON, api_key="k", fetch=lambda *a: _reponse(None, None))
        assert s is None


class TestOverrideExploitable:
    def test_solar_prime_sur_estimation_vision(self):
        vision = {
            "toiture": {"presente": True, "type": "plate", "surface_estimee_m2": 300},
            "parking": {"present": False},
        }
        a = analyser_potentiels(
            latitude=_LAT, longitude=_LON, vision=vision,
            surface_batie_m2=2000, surface_exploitable_m2=1400,
        )
        # exploitable 1400 → palier 7, +2 plate = 9 (et pas le ratio Vision)
        assert a.solaire.surface_exploitable_m2 == 1400
        assert a.solaire.score == 9
