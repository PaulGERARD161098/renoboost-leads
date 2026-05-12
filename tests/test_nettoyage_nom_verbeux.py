"""Tests B6 — nettoyage des noms commerciaux verbeux avant matching SIREN.

Problème observé sur le proto Nord 59 (10/05) : les noms Places enrichis avec
une description technique (ex : "SMI mécanique et outillage de précision
fraisage 5 axes...") ne matchent plus la raison sociale courte de SIRENE
("SMI" ou "SMI MECANIQUE PRECISION").

Heuristique : on coupe le nom au 1er mot descriptif (métier, secteur, mot
fonctionnel) trouvé en position ≥ 1, et on garde tout ce qui le précède.
"""

from __future__ import annotations

import pytest

from renoboost_leads.stage2_entreprises.matcher import (
    SEUIL_CONFIANCE,
    _nettoyer_nom_commercial,
    scorer_candidat,
    selectionner_meilleur_candidat,
)


class TestNettoyageNomCommercial:
    def test_nom_verbeux_smi_coupe_apres_marque(self):
        nom = "SMI mécanique et outillage de précision fraisage 5 axes"
        assert _nettoyer_nom_commercial(nom) == "SMI"

    def test_nom_court_inchange(self):
        assert _nettoyer_nom_commercial("Hôtel Le Sud") == "Hôtel Le Sud"

    def test_mot_descriptif_en_position_0_ne_coupe_pas(self):
        # Risque sinon : chaîne vide → tout match avec tout
        nom = "Mécanique Précision SARL"
        assert _nettoyer_nom_commercial(nom) == "Mécanique Précision SARL"

    def test_none_renvoie_vide(self):
        assert _nettoyer_nom_commercial(None) == ""

    def test_chaine_vide(self):
        assert _nettoyer_nom_commercial("") == ""

    @pytest.mark.parametrize(
        "nom,attendu",
        [
            ("ACME industrie et services SARL", "ACME"),
            ("Dupont chaudronnerie", "Dupont"),
            ("Martin Frères tournage usinage", "Martin Frères"),
            ("Atelier Lambert soudure", "Atelier Lambert"),
            ("BTP Construction Sud", "BTP Construction Sud"),  # pas de mot stop
            ("Foo bar fabrication production", "Foo bar"),
        ],
    )
    def test_cas_reels(self, nom, attendu):
        assert _nettoyer_nom_commercial(nom) == attendu

    def test_insensible_aux_accents(self):
        # "mecanique" sans accent doit aussi couper
        assert _nettoyer_nom_commercial("SMI mecanique outillage") == "SMI"

    def test_insensible_a_la_casse(self):
        assert _nettoyer_nom_commercial("SMI MECANIQUE OUTILLAGE") == "SMI"


class TestScoringAvecNomVerbeux:
    def test_smi_verbeux_match_smi_court(self):
        """Avant le fix B6, le score nom passait à 0 ou 8 → total < 60.

        Après B6 : nom_cible et nom_cand sont nettoyés symétriquement,
        le matching de Levenshtein redevient discriminant.
        """
        candidat = {
            "nom_complet": "SMI MECANIQUE PRECISION SAS",
            "etat_administratif": "A",
            "nature_juridique": "5710",
            "siege": {"code_postal": "59000", "libelle_commune": "Lille"},
            "siren": "402222222",
        }
        sd = scorer_candidat(
            candidat,
            nom_cible="SMI mécanique et outillage de précision fraisage 5 axes",
            code_postal_cible="59000",
            ville_cible="Lille",
        )
        # Adresse 50 + Nom 30 (SMI vs SMI après nettoyage) + Statut 20 + Forme 10 = 110
        assert sd.score >= SEUIL_CONFIANCE
        assert sd.detail["nom"] >= 18  # au moins le palier 0.6


class TestSelectionAvecNomVerbeux:
    def test_smi_verbeux_choisit_le_bon_siren(self):
        candidats = [
            # Distracteur : autre boîte du Nord
            {
                "nom_complet": "DURAND ET FILS",
                "siege": {"code_postal": "59000", "libelle_commune": "Lille"},
                "etat_administratif": "A",
                "nature_juridique": "5499",
                "siren": "111111111",
            },
            # Vrai match : SMI MECANIQUE PRECISION
            {
                "nom_complet": "SMI MECANIQUE PRECISION SAS",
                "siege": {"code_postal": "59000", "libelle_commune": "Lille"},
                "etat_administratif": "A",
                "nature_juridique": "5710",
                "siren": "402222222",
            },
        ]
        result, score, incertain = selectionner_meilleur_candidat(
            candidats,
            nom_cible="SMI mécanique et outillage de précision fraisage 5 axes",
            code_postal_cible="59000",
            ville_cible="Lille",
        )
        assert result is not None
        assert result["siren"] == "402222222"
        assert score >= SEUIL_CONFIANCE
        assert incertain is False
