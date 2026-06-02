"""Tests du repli libellé NAF (division)."""

from __future__ import annotations

from renoboost_leads.common.naf import NAF_DIVISIONS, libelle_naf_pour_code


class TestLibelleNafPourCode:
    def test_sous_classe(self):
        assert libelle_naf_pour_code("10.13A") == "Industries alimentaires"

    def test_division_nue(self):
        assert libelle_naf_pour_code("46") == (
            "Commerce de gros, à l'exception des automobiles et des motocycles"
        )

    def test_format_sans_point(self):
        assert libelle_naf_pour_code("2562B") == (
            "Fabrication de produits métalliques, sauf machines et équipements"
        )

    def test_code_inconnu(self):
        assert libelle_naf_pour_code("04.00Z") is None  # division 04 n'existe pas

    def test_none_et_vide(self):
        assert libelle_naf_pour_code(None) is None
        assert libelle_naf_pour_code("") is None
        assert libelle_naf_pour_code("X") is None

    def test_table_couvre_sections_cles(self):
        # Quelques divisions structurantes pour les verticales énergie/industrie.
        for code in ("10", "20", "25", "35", "41", "43", "47", "49", "52"):
            assert code in NAF_DIVISIONS
