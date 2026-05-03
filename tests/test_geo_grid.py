"""Tests unitaires du maillage géographique."""

from __future__ import annotations

import pytest

from renoboost_leads.models import Zone
from renoboost_leads.stage1_decouverte.geo_grid import (
    grille_pour_bbox,
    grille_pour_zone,
)


class TestGrillePourBbox:
    def test_grille_simple(self):
        # Petite bbox sur l'Hérault
        points = grille_pour_bbox(
            sw_lat=43.20,
            sw_lng=2.55,
            ne_lat=44.05,
            ne_lng=4.20,
            pas_km=20,
            rayon_km=10,
        )
        assert len(points) > 0
        for p in points:
            assert 43.20 <= p.latitude <= 44.10
            assert 2.55 <= p.longitude <= 4.25
            assert p.rayon_km == 10

    def test_pas_plus_grand_que_zone(self):
        # Zone très petite — au moins 1 point
        points = grille_pour_bbox(
            sw_lat=43.50,
            sw_lng=3.50,
            ne_lat=43.55,
            ne_lng=3.55,
            pas_km=10,
            rayon_km=5,
        )
        assert len(points) >= 1

    def test_bbox_invalide_leve_erreur(self):
        with pytest.raises(ValueError, match="Bbox invalide"):
            grille_pour_bbox(
                sw_lat=44.0,
                sw_lng=3.0,
                ne_lat=43.0,
                ne_lng=2.0,  # SW > NE
                pas_km=10,
                rayon_km=5,
            )

    def test_labels_uniques(self):
        points = grille_pour_bbox(
            sw_lat=43.20,
            sw_lng=2.55,
            ne_lat=44.05,
            ne_lng=4.20,
            pas_km=20,
            rayon_km=10,
            label_prefix="test_",
        )
        labels = [p.label for p in points]
        assert len(labels) == len(set(labels)), "Labels doivent être uniques"
        assert all(lbl.startswith("test_") for lbl in labels)


class TestGrillePourZone:
    def test_departement_herault(self):
        zone = Zone(type="departement", codes=["34"], rayon_par_point_km=10, pas_grille_km=15)
        points = grille_pour_zone(zone)
        assert len(points) > 0
        # Rayon respecté
        assert all(p.rayon_km == 10 for p in points)
        # Latitudes plausibles pour l'Hérault
        assert all(43.0 < p.latitude < 44.5 for p in points)

    def test_departement_inconnu_leve_erreur(self):
        zone = Zone(
            type="departement",
            codes=["999"],
            rayon_par_point_km=10,
            pas_grille_km=15,
        )
        with pytest.raises(ValueError, match="Département inconnu"):
            grille_pour_zone(zone)

    def test_type_zone_non_supporte(self):
        zone = Zone(type="france", codes=["FR"], rayon_par_point_km=10, pas_grille_km=15)
        with pytest.raises(NotImplementedError):
            grille_pour_zone(zone)

    def test_plusieurs_departements(self):
        zone = Zone(
            type="departement",
            codes=["34", "30"],  # Hérault + Gard
            rayon_par_point_km=10,
            pas_grille_km=20,
        )
        points = grille_pour_zone(zone)
        # Devrait y avoir des points pour les deux départements
        labels_dpt = {p.label.split("_")[0] for p in points}
        assert "dpt34" in labels_dpt
        assert "dpt30" in labels_dpt
