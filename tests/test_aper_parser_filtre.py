"""Tests parser + filtre parkings APER sur la fixture de démo."""

from __future__ import annotations

from pathlib import Path

import pytest

from renoboost_leads.parkings_aper.filtre_parkings import filtrer_parkings
from renoboost_leads.parkings_aper.models import AperConfig
from renoboost_leads.parkings_aper.parser_parkings import (
    ParseParkingsError,
    lire_csv_parkings,
)

FIXTURE = Path(__file__).parent / "fixtures_parkings" / "echantillon_parkings_demo.csv"


class TestParser:
    def test_lit_toutes_les_lignes(self):
        res = lire_csv_parkings(FIXTURE)
        assert res.nb_lignes_brutes == 10
        assert res.nb_lignes_valides == 10
        assert not res.erreurs

    def test_surface_parsee_en_float(self):
        res = lire_csv_parkings(FIXTURE)
        carrefour = next(lg for lg in res.lignes if lg.nom == "Carrefour Lens")
        assert carrefour.surface_m2 == 14500.0
        assert carrefour.code_postal == "62300"

    def test_siren_normalise(self):
        res = lire_csv_parkings(FIXTURE)
        usine = next(lg for lg in res.lignes if lg.nom == "Usine Plastiques Nord")
        assert usine.siren == "402111111"

    def test_fichier_introuvable(self):
        with pytest.raises(ParseParkingsError):
            lire_csv_parkings(Path("/nope/nada.csv"))

    def test_surface_avec_virgule_decimale(self, tmp_path):
        p = tmp_path / "v.csv"
        p.write_text("NOM;SURFACE_M2\nTest;1 600,5\n", encoding="utf-8-sig")
        res = lire_csv_parkings(p)
        assert res.lignes[0].surface_m2 == 1600.5


class TestFiltre:
    def test_garde_au_dessus_du_seuil(self):
        res = lire_csv_parkings(FIXTURE)
        retenues, rejets = filtrer_parkings(res.lignes)
        # 10 lignes − 2 petits parkings (850, 420 m²) = 8
        assert len(retenues) == 8
        assert rejets["surface_insuffisante"] == 2

    def test_seuil_personnalise(self):
        res = lire_csv_parkings(FIXTURE)
        retenues, _ = filtrer_parkings(
            res.lignes, AperConfig(surface_min_m2=10000)
        )
        # surfaces > 10000 : 14500, 22000, 31000, 12500 = 4
        assert len(retenues) == 4
