"""Tests porte a — connecteur géo OSM (Overpass) → CSV d'inventaire parkings."""

from __future__ import annotations

import pytest

from renoboost_leads.parkings_aper.connecteur_geo import (
    Bbox,
    OverpassClientDryRun,
    ecrire_inventaire_csv,
    element_osm_vers_ligne,
    recuperer_parkings,
    surface_polygone_m2,
)
from renoboost_leads.parkings_aper.parser_parkings import lire_csv_parkings


class TestBbox:
    def test_parse_ok(self):
        b = Bbox.depuis_str("50.40,2.80,50.55,2.95")
        assert (b.sud, b.ouest, b.nord, b.est) == (50.40, 2.80, 50.55, 2.95)
        assert b.as_overpass() == "50.4,2.8,50.55,2.95"

    def test_parse_invalide(self):
        with pytest.raises(ValueError):
            Bbox.depuis_str("50.4,2.8")


class TestSurface:
    def test_carre_equateur(self):
        # ~0.001° × 0.001° à l'équateur ≈ 111,2 m × 111,2 m ≈ 12 365 m²
        pts = [(0.0, 0.0), (0.0, 0.001), (0.001, 0.001), (0.001, 0.0)]
        aire = surface_polygone_m2(pts)
        assert 11_500 < aire < 13_000

    def test_polygone_degenere(self):
        assert surface_polygone_m2([(0.0, 0.0), (0.0, 0.001)]) == 0.0


class TestTransform:
    def test_element_vers_ligne(self):
        el = OverpassClientDryRun().chercher_parkings(Bbox(0, 0, 1, 1))[0]
        ligne = element_osm_vers_ligne(el)
        assert ligne is not None
        assert ligne.identifiant == "osm:way/1001"
        assert ligne.nom == "Parking Carrefour Lens"
        assert ligne.code_postal == "62300"
        assert ligne.surface_m2 > 10_000  # grand parking → échéance 2026
        assert ligne.source == "aper_osm"

    def test_geometrie_insuffisante_rejetee(self):
        assert element_osm_vers_ligne({"id": 9, "geometry": [{"lat": 1, "lon": 1}]}) is None


class TestRecuperer:
    def test_filtre_seuil_defaut(self):
        # Dry-run : 1 grand parking (~11k m²) + 1 petit (~700 m²) → seuil 1500 garde 1.
        lignes = recuperer_parkings(Bbox(0, 0, 1, 1), client=OverpassClientDryRun())
        assert len(lignes) == 1
        assert lignes[0].identifiant == "osm:way/1001"

    def test_seuil_bas_garde_tout(self):
        lignes = recuperer_parkings(
            Bbox(0, 0, 1, 1), client=OverpassClientDryRun(), surface_min_m2=100
        )
        assert len(lignes) == 2

    def test_fenetre_surface_exclut_les_gros(self):
        # Fenêtre [100, 1000] : ne garde que le petit parking (~700 m²),
        # le grand (~11k m²) est écarté dès la découverte.
        lignes = recuperer_parkings(
            Bbox(0, 0, 1, 1), client=OverpassClientDryRun(),
            surface_min_m2=100, surface_max_m2=1000,
        )
        assert len(lignes) == 1
        assert lignes[0].surface_m2 < 1000


class TestCsvRoundTrip:
    def test_ecrire_puis_relire(self, tmp_path):
        lignes = recuperer_parkings(
            Bbox(0, 0, 1, 1), client=OverpassClientDryRun(), surface_min_m2=100
        )
        out = ecrire_inventaire_csv(lignes, tmp_path / "inventaire.csv")
        assert out.exists()
        # Le CSV doit être relisible par le parser APER standard.
        res = lire_csv_parkings(out)
        assert res.nb_lignes_valides == 2
        surfaces = sorted(round(line.surface_m2) for line in res.lignes)
        assert surfaces[1] > 10_000  # le grand parking est préservé


class TestDryRunClient:
    def test_health_check(self):
        ok, _ = OverpassClientDryRun().health_check()
        assert ok is True
