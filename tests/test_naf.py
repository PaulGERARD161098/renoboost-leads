"""Tests du repli libellé NAF (division)."""

from __future__ import annotations

from renoboost_leads.common.naf import (
    NAF_DIVISIONS,
    est_code_ape_complet,
    libelle_naf_pour_code,
    section_pour_code,
    sections_pour_codes,
)


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


class TestEstCodeApeComplet:
    def test_codes_complets(self):
        for c in ("25.11Z", "2511Z", "46.90Z", "70.10Z"):
            assert est_code_ape_complet(c) is True

    def test_prefixes_et_divisions(self):
        for c in ("10", "25", "70.10", "6820", "47"):
            assert est_code_ape_complet(c) is False

    def test_none_et_vide(self):
        assert est_code_ape_complet(None) is False
        assert est_code_ape_complet("") is False


class TestSections:
    def test_section_par_division(self):
        assert section_pour_code("10") == "C"   # industrie manufacturière
        assert section_pour_code("33") == "C"
        assert section_pour_code("49") == "H"   # transports
        assert section_pour_code("70.10") == "M"  # sièges sociaux
        assert section_pour_code("47") == "G"   # commerce

    def test_section_code_complet(self):
        assert section_pour_code("25.11Z") == "C"

    def test_section_inconnue(self):
        assert section_pour_code("04") is None
        assert section_pour_code(None) is None

    def test_sections_pour_codes_dedup_trie(self):
        # Cible rossini : divisions 10..33 (C) + 49/52/53 (H) + 70.10 (M).
        codes = ["10", "20", "25", "33", "49", "52", "53", "70.10"]
        assert sections_pour_codes(codes) == ["C", "H", "M"]
