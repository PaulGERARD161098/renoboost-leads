"""Tests parser CSV AAA Data."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from renoboost_leads.veille_immatriculations.models import (
    ENERGIES_ELECTRIQUES,
    TYPES_ACQUEREUR_MORALE,
    LigneAAA,
    VeilleConfig,
    parse_date_aaa,
)
from renoboost_leads.veille_immatriculations.parser_aaa import (
    ParseErrorAAA,
    lire_csv_aaa,
)

FIXTURE = Path(__file__).parent / "fixtures_aaa" / "echantillon_aaa_demo.csv"


class TestParseDateAAA:
    def test_iso(self):
        assert parse_date_aaa("2026-05-13", ["%Y-%m-%d"]) == date(2026, 5, 13)

    def test_fr_slash(self):
        assert parse_date_aaa("13/05/2026", ["%Y-%m-%d", "%d/%m/%Y"]) == date(2026, 5, 13)

    def test_invalide_leve(self):
        with pytest.raises(ValueError, match="Date AAA non parseable"):
            parse_date_aaa("pas-une-date", ["%Y-%m-%d"])


class TestLigneAAANormalisation:
    def test_siren_extrait_du_siret(self):
        ligne = LigneAAA(
            date_immatriculation=date(2026, 5, 13),
            energie="EL",
            type_acquereur="M",
            siren="40211111100025",  # SIRET
        )
        assert ligne.siren == "402111111"  # gardé les 9 premiers

    def test_siren_non_numerique_ecarte(self):
        ligne = LigneAAA(
            date_immatriculation=date(2026, 5, 13),
            energie="EL",
            type_acquereur="M",
            siren="ABC123",
        )
        assert ligne.siren is None

    def test_code_postal_pad_zero(self):
        ligne = LigneAAA(
            date_immatriculation=date(2026, 5, 13),
            energie="EL",
            type_acquereur="M",
            code_postal="1000",
        )
        assert ligne.code_postal == "01000"

    def test_energie_majuscule(self):
        ligne = LigneAAA(
            date_immatriculation=date(2026, 5, 13), energie=" el ", type_acquereur="M"
        )
        assert ligne.energie == "EL"

    def test_type_acquereur_majuscule(self):
        ligne = LigneAAA(
            date_immatriculation=date(2026, 5, 13), energie="EL", type_acquereur="m"
        )
        assert ligne.type_acquereur == "M"


class TestLireCsvAAA:
    def test_fichier_inexistant_leve(self, tmp_path):
        with pytest.raises(ParseErrorAAA, match="introuvable"):
            lire_csv_aaa(tmp_path / "absent.csv")

    def test_fixture_parsee_correctement(self):
        result = lire_csv_aaa(FIXTURE)
        # 10 lignes attendues
        assert result.nb_lignes_brutes == 10
        assert result.nb_lignes_valides == 10
        assert not result.erreurs

    def test_marques_modeles_extraits(self):
        result = lire_csv_aaa(FIXTURE)
        marques = {lead.marque for lead in result.lignes}
        assert "TESLA" in marques
        assert "RENAULT" in marques
        assert "PEUGEOT" in marques

    def test_dates_parsees(self):
        result = lire_csv_aaa(FIXTURE)
        assert all(lead.date_immatriculation == date(2026, 5, 13) for lead in result.lignes)

    def test_sirens_normalises(self):
        result = lire_csv_aaa(FIXTURE)
        sirens = [lead.siren for lead in result.lignes if lead.siren]
        assert "402111111" in sirens
        assert "503333333" in sirens
        # Particulier sans SIREN
        assert any(lead.siren is None and lead.type_acquereur == "P" for lead in result.lignes)

    def test_aucune_colonne_attendue_leve(self, tmp_path):
        bad = tmp_path / "bad.csv"
        bad.write_text("foo;bar;baz\n1;2;3\n", encoding="utf-8")
        with pytest.raises(ParseErrorAAA, match="Aucune colonne attendue"):
            lire_csv_aaa(bad)

    def test_mapping_colonnes_custom(self, tmp_path):
        """Si AAA livre des colonnes différentes, on remappe sans toucher au code."""
        csv = tmp_path / "custom.csv"
        csv.write_text(
            "dateImmat,energie,acquereur,siren_num\n"
            "2026-05-13,EL,M,402111111\n",
            encoding="utf-8",
        )
        cfg = VeilleConfig(
            separateur=",",
            mapping_colonnes={
                "dateImmat": "date_immatriculation",
                "energie": "energie",
                "acquereur": "type_acquereur",
                "siren_num": "siren",
            },
        )
        result = lire_csv_aaa(csv, cfg)
        assert result.nb_lignes_valides == 1
        assert result.lignes[0].siren == "402111111"


class TestConstantesAAA:
    def test_energies_electriques_couvre_principaux(self):
        for code in ("EL", "HE", "HH"):
            assert code in ENERGIES_ELECTRIQUES

    def test_types_acquereur_morale(self):
        for code in ("M", "PM"):
            assert code in TYPES_ACQUEREUR_MORALE
