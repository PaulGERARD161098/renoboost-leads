"""Tests filtre VE flotte entreprise."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from renoboost_leads.veille_immatriculations.filtre_ve_flotte import (
    est_ve_flotte_entreprise,
    filtrer_lignes_aaa,
)
from renoboost_leads.veille_immatriculations.models import LigneAAA, VeilleConfig
from renoboost_leads.veille_immatriculations.parser_aaa import lire_csv_aaa

FIXTURE = Path(__file__).parent / "fixtures_aaa" / "echantillon_aaa_demo.csv"


def _ligne(energie: str = "EL", acquereur: str = "M", siren: str | None = "402111111") -> LigneAAA:
    return LigneAAA(
        date_immatriculation=date(2026, 5, 13),
        energie=energie,
        type_acquereur=acquereur,
        siren=siren,
    )


class TestEstVEFlotteEntreprise:
    def test_ve_pur_morale_avec_siren_passe(self):
        ok, raison = est_ve_flotte_entreprise(_ligne("EL", "M", "402111111"), VeilleConfig())
        assert ok is True
        assert raison is None

    def test_phev_passe_par_defaut(self):
        ok, _ = est_ve_flotte_entreprise(_ligne("HE", "M", "402111111"), VeilleConfig())
        assert ok is True

    def test_essence_rejete(self):
        ok, raison = est_ve_flotte_entreprise(_ligne("ES", "M", "402111111"), VeilleConfig())
        assert ok is False
        assert "energie" in raison.lower()

    def test_particulier_rejete(self):
        ok, raison = est_ve_flotte_entreprise(_ligne("EL", "P", "402111111"), VeilleConfig())
        assert ok is False
        assert "acquereur" in raison.lower()

    def test_siren_absent_rejete(self):
        ok, raison = est_ve_flotte_entreprise(_ligne("EL", "M", None), VeilleConfig())
        assert ok is False
        assert "SIREN" in raison

    def test_siren_absent_non_exige_passe(self):
        cfg = VeilleConfig(exiger_siren=False)
        ok, _ = est_ve_flotte_entreprise(_ligne("EL", "M", None), cfg)
        assert ok is True


class TestFiltrerLignes:
    def test_fixture_filtre_distingue_bien(self):
        # Fixture : 10 lignes, dont :
        # - 7 VE/HE/HH + perso morale + SIREN → retenues
        # - 1 essence morale → rejet (energie)
        # - 1 hybride particulier → rejet (acquereur)
        # - 1 électrique morale sans SIREN → rejet (SIREN absent)
        result = lire_csv_aaa(FIXTURE)
        retenues, rejets = filtrer_lignes_aaa(result.lignes, VeilleConfig())
        assert len(retenues) == 7
        assert rejets.get("energie", 0) == 1
        assert rejets.get("acquereur", 0) == 1
        assert rejets.get("SIREN absent", 0) == 1

    def test_filtre_sur_liste_vide(self):
        retenues, rejets = filtrer_lignes_aaa([], VeilleConfig())
        assert retenues == []
        assert rejets == {}
