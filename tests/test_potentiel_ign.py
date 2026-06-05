"""Tests du connecteur IGN emprise bâtie (calcul d'aire, sans réseau)."""

from __future__ import annotations

from renoboost_leads.potentiel.ign import (
    _aire_polygone_m2,
    surface_batie_depuis_geojson,
    surface_batie_m2,
)

# Carré ~100 m de côté autour de (50.6292, 3.0573).
_LAT, _LON = 50.6292, 3.0573
_D = 50.0 / 110540.0  # ~50 m en degrés de latitude


def _carre(centre_lat, centre_lon, demi_m):
    dlat = demi_m / 110540.0
    import math
    dlon = demi_m / (111320.0 * math.cos(math.radians(centre_lat)))
    return [
        [centre_lon - dlon, centre_lat - dlat],
        [centre_lon + dlon, centre_lat - dlat],
        [centre_lon + dlon, centre_lat + dlat],
        [centre_lon - dlon, centre_lat + dlat],
        [centre_lon - dlon, centre_lat - dlat],
    ]


def _geojson(anneau):
    return {"features": [{"geometry": {"type": "Polygon", "coordinates": [anneau]}}]}


def test_aire_carre_100m():
    aire = _aire_polygone_m2(_carre(_LAT, _LON, 50.0), _LAT)
    assert 9000 < aire < 11000  # ~100 m × 100 m = 10 000 m²


def test_surface_batiment_contenant_le_point():
    gj = _geojson(_carre(_LAT, _LON, 50.0))
    s = surface_batie_depuis_geojson(_LAT, _LON, gj)
    assert s is not None and 9000 < s < 11000


def test_point_hors_batiment_repli_plus_grand():
    # Le point est loin du carré → repli sur le plus grand bâtiment de la fenêtre.
    gj = _geojson(_carre(_LAT + 0.01, _LON + 0.01, 30.0))
    s = surface_batie_depuis_geojson(_LAT, _LON, gj)
    assert s is not None and s > 0


def test_aucun_batiment_renvoie_none():
    assert surface_batie_depuis_geojson(_LAT, _LON, {"features": []}) is None


def test_fetch_injecte():
    s = surface_batie_m2(_LAT, _LON, fetch=lambda la, lo: _geojson(_carre(_LAT, _LON, 50.0)))
    assert s is not None and 9000 < s < 11000


def test_fetch_en_erreur_renvoie_none():
    def boom(la, lo):
        raise RuntimeError("réseau coupé")

    assert surface_batie_m2(_LAT, _LON, fetch=boom) is None
