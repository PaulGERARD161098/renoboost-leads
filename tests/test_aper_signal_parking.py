"""Tests jointure « signal parking » (couche qualité du mix, incrément 3)."""

from __future__ import annotations

from renoboost_leads.parkings_aper.models import LigneParking
from renoboost_leads.parkings_aper.signal_parking import (
    LeadGeo,
    annoter_signal_parking,
    chercher_parking_qualifiant,
    distance_m,
)

# Point de référence : un site PME fictif.
LAT, LON = 50.6300, 2.9700


def _parking(surface: float, dlat: float = 0.0, dlon: float = 0.0) -> LigneParking:
    return LigneParking(surface_m2=surface, latitude=LAT + dlat, longitude=LON + dlon)


class TestDistance:
    def test_distance_nulle(self):
        assert distance_m(LAT, LON, LAT, LON) == 0.0

    def test_ordre_de_grandeur(self):
        # ~0.001° de latitude ≈ 111 m.
        d = distance_m(LAT, LON, LAT + 0.001, LON)
        assert 100 < d < 125


class TestChercherQualifiant:
    def test_parking_dans_fenetre_et_rayon(self):
        # Parking 600 m² à ~20 m → qualifiant.
        parkings = [_parking(600, dlat=0.0002)]
        res = chercher_parking_qualifiant(LAT, LON, parkings)
        assert res.qualifiant is True
        assert res.surface_m2 == 600
        assert res.distance_m is not None and res.distance_m < 80

    def test_trop_grand_exclu(self):
        # 5000 m² (hors fenêtre haute) → pas qualifiant même tout près.
        res = chercher_parking_qualifiant(LAT, LON, [_parking(5000, dlat=0.0001)])
        assert res.qualifiant is False

    def test_trop_petit_exclu(self):
        res = chercher_parking_qualifiant(LAT, LON, [_parking(100, dlat=0.0001)])
        assert res.qualifiant is False

    def test_hors_rayon_exclu(self):
        # 600 m² mais à ~330 m (0.003°) → hors rayon 80 m.
        res = chercher_parking_qualifiant(LAT, LON, [_parking(600, dlat=0.003)])
        assert res.qualifiant is False

    def test_choisit_le_plus_proche(self):
        parkings = [
            _parking(700, dlat=0.0005),   # plus loin (~55 m)
            _parking(500, dlat=0.0001),   # plus proche (~11 m)
        ]
        res = chercher_parking_qualifiant(LAT, LON, parkings)
        assert res.qualifiant is True
        assert res.surface_m2 == 500  # le plus proche prime


class TestAnnoter:
    def test_stats_et_sans_coords(self):
        leads = [
            LeadGeo(cle="A", latitude=LAT, longitude=LON),          # qualifiant
            LeadGeo(cle="B", latitude=LAT + 0.05, longitude=LON),    # loin → non
            LeadGeo(cle="C", latitude=None, longitude=None),         # sans coords → absent
        ]
        parkings = [_parking(600, dlat=0.0001)]
        res = annoter_signal_parking(leads, parkings)
        assert res["A"].qualifiant is True
        assert res["B"].qualifiant is False
        assert "C" not in res  # lead sans coordonnées non annoté
