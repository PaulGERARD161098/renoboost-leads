"""Tests parser CSV générique (auto-détection + mapping heuristique)."""

from __future__ import annotations

import pytest

from renoboost_leads.veille_immatriculations.parser_generique import (
    _normaliser_pour_match,
    _proposer_mapping,
    detecter_format_csv,
    lire_csv_avec_detection,
)


class TestNormaliser:
    def test_accents_supprimes(self):
        assert _normaliser_pour_match("Modèle Véhicule") == "modele_vehicule"

    def test_espaces_remplaces(self):
        assert _normaliser_pour_match("Date Immatriculation") == "date_immatriculation"

    def test_lowercase(self):
        assert _normaliser_pour_match("CODE_POSTAL") == "code_postal"


class TestProposerMapping:
    def test_colonnes_aaa_standards(self):
        cols = [
            "DATE_IMMATRICULATION",
            "MARQUE",
            "MODELE",
            "ENERGIE",
            "TYPE_ACQUEREUR",
            "SIREN",
            "RAISON_SOCIALE",
            "CODE_POSTAL",
        ]
        mapping, non_mappees, manquants = _proposer_mapping(cols)
        assert mapping["DATE_IMMATRICULATION"] == "date_immatriculation"
        assert mapping["MARQUE"] == "marque"
        assert mapping["ENERGIE"] == "energie"
        assert mapping["TYPE_ACQUEREUR"] == "type_acquereur"
        assert mapping["SIREN"] == "siren"
        assert manquants == []

    def test_colonnes_avec_accents_et_espaces(self):
        cols = ["Date Immatriculation", "Modèle", "Énergie", "Type Acquéreur"]
        mapping, _, manquants = _proposer_mapping(cols)
        assert mapping["Date Immatriculation"] == "date_immatriculation"
        assert mapping["Énergie"] == "energie"
        assert mapping["Type Acquéreur"] == "type_acquereur"
        # Modele OK, mais date+energie+acquereur OK → manquants = []
        assert manquants == []

    def test_colonnes_anglaises(self):
        cols = ["date", "brand", "model", "energy", "fuel", "siren"]
        mapping, _, manquants = _proposer_mapping(cols)
        assert mapping["brand"] == "marque"
        assert mapping["model"] == "modele"
        # energy OU fuel devrait mapper energie (un seul gardé)
        assert any(v == "energie" for v in mapping.values())
        # type_acquereur manquant
        assert "type_acquereur" in manquants

    def test_colonnes_inconnues_listees(self):
        cols = ["DATE", "ENERGIE", "TYPE_ACQUEREUR", "FOO_BIZARRE", "BAR_INUTILE"]
        mapping, non_mappees, _ = _proposer_mapping(cols)
        assert "FOO_BIZARRE" in non_mappees
        assert "BAR_INUTILE" in non_mappees

    def test_pas_de_doublons_dans_mapping(self):
        # Deux colonnes pourraient matcher "energie" → on garde la première
        cols = ["ENERGIE", "ENERGY", "TYPE_ACQUEREUR", "DATE"]
        mapping, _, _ = _proposer_mapping(cols)
        valeurs = list(mapping.values())
        assert len(valeurs) == len(set(valeurs))


class TestDetecterFormat:
    def test_csv_aaa_standard(self, tmp_path):
        csv = tmp_path / "aaa.csv"
        csv.write_text(
            "DATE_IMMATRICULATION;MARQUE;ENERGIE;TYPE_ACQUEREUR;SIREN\n"
            "2026-05-13;TESLA;EL;M;402111111\n",
            encoding="utf-8",
        )
        det = detecter_format_csv(csv)
        assert det.separateur_detecte == ";"
        assert det.encodage_detecte in ("utf-8", "utf-8-sig")
        assert det.utilisable
        assert "MARQUE" in det.mapping_propose

    def test_csv_anglais_virgule(self, tmp_path):
        csv = tmp_path / "en.csv"
        csv.write_text(
            "date,brand,energy,acquereur,siren\n"
            "2026-05-13,TESLA,EL,M,402111111\n",
            encoding="utf-8",
        )
        det = detecter_format_csv(csv)
        assert det.separateur_detecte == ","
        assert det.utilisable

    def test_csv_latin1_utf8sig(self, tmp_path):
        # Certains exports Excel collent un BOM utf-8
        csv = tmp_path / "bom.csv"
        csv.write_bytes(
            b"\xef\xbb\xbfDATE_IMMATRICULATION;ENERGIE;TYPE_ACQUEREUR;SIREN\n"
            b"2026-05-13;EL;M;402111111\n"
        )
        det = detecter_format_csv(csv)
        assert det.encodage_detecte == "utf-8-sig"

    def test_csv_champs_obligatoires_manquants(self, tmp_path):
        csv = tmp_path / "incomplet.csv"
        csv.write_text("MARQUE;MODELE;PLAQUE\nTESLA;MODEL Y;FZ-123-AB\n", encoding="utf-8")
        det = detecter_format_csv(csv)
        assert not det.utilisable
        assert "date_immatriculation" in det.champs_manquants
        assert "energie" in det.champs_manquants

    def test_fichier_inexistant_leve(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            detecter_format_csv(tmp_path / "absent.csv")


class TestLireAvecDetection:
    def test_pipeline_complet(self, tmp_path):
        csv = tmp_path / "auto.csv"
        csv.write_text(
            "Date Immatriculation;Marque;Modèle;Énergie;Type Acquéreur;SIREN;Raison Sociale\n"
            "2026-05-13;TESLA;MODEL Y;EL;M;402111111;SMI INDUSTRIE\n"
            "2026-05-13;RENAULT;ZOE;EL;M;503333333;HOTEL FLANDRES\n",
            encoding="utf-8",
        )
        lignes, det = lire_csv_avec_detection(csv)
        assert det.utilisable
        assert len(lignes) == 2
        assert lignes[0].marque == "TESLA"
        assert lignes[1].siren == "503333333"

    def test_leve_si_manquant(self, tmp_path):
        csv = tmp_path / "incomplet.csv"
        csv.write_text("MARQUE\nTESLA\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Impossible de mapper"):
            lire_csv_avec_detection(csv)
