"""Tests unitaires du matcher SIREN (étage 2)."""

from __future__ import annotations

from renoboost_leads.stage2_entreprises.matcher import (
    SEUIL_CONFIANCE,
    _levenshtein_similarity,
    _normaliser,
    scorer_candidat,
    selectionner_meilleur_candidat,
)
from renoboost_leads.stage2_entreprises.referentiel_chaines import detecter_chaine


class TestNormalisation:
    def test_minuscules_accents(self):
        assert _normaliser("Hôtel LE Sud") == "hotel le sud"

    def test_ponctuation(self):
        assert _normaliser("S.A.R.L. Foo-Bar") == "s a r l foo bar"

    def test_none_renvoie_vide(self):
        assert _normaliser(None) == ""


class TestLevenshtein:
    def test_identiques(self):
        assert _levenshtein_similarity("abc", "abc") == 1.0

    def test_completement_differents(self):
        assert _levenshtein_similarity("abc", "xyz") < 0.5

    def test_proche(self):
        # 1 substitution sur 4 caractères ≈ 0.75
        assert _levenshtein_similarity("hôtel", "hotel") > 0.7

    def test_un_vide(self):
        assert _levenshtein_similarity("", "abc") == 0.0
        assert _levenshtein_similarity("abc", "") == 0.0


class TestScoring:
    def test_score_parfait(self):
        candidat = {
            "nom_complet": "HOTEL LE SUD",
            "etat_administratif": "A",
            "nature_juridique": "5710",  # SAS
            "siege": {
                "code_postal": "34000",
                "libelle_commune": "Montpellier",
            },
        }
        sd = scorer_candidat(
            candidat, nom_cible="Hôtel Le Sud",
            code_postal_cible="34000",
            ville_cible="Montpellier",
        )
        # Adresse 50 + Nom 30 + Statut 20 + Forme 10 = 110
        assert sd.score >= 100

    def test_score_faible(self):
        candidat = {
            "nom_complet": "AUTRE TRUC",
            "etat_administratif": "C",  # Cessé
            "siege": {"code_postal": "75001"},
        }
        sd = scorer_candidat(
            candidat, nom_cible="Hôtel Le Sud",
            code_postal_cible="34000",
            ville_cible="Montpellier",
        )
        assert sd.score < SEUIL_CONFIANCE

    def test_meme_departement_demi_score_adresse(self):
        candidat = {
            "nom_complet": "HOTEL LE SUD",
            "siege": {"code_postal": "34070"},  # même dpt mais autre commune
            "etat_administratif": "A",
            "nature_juridique": "5710",
        }
        sd = scorer_candidat(
            candidat, nom_cible="Hôtel Le Sud",
            code_postal_cible="34000",
            ville_cible="Montpellier",
        )
        # CP différent mais même dpt 34 → 10 pts adresse
        # + Nom 30 + Statut 20 + Forme 10 = 70
        assert 60 <= sd.score <= 80


class TestSelectionMeilleur:
    def test_liste_vide(self):
        result, score, incertain = selectionner_meilleur_candidat([], "X", "00000", "Y")
        assert result is None
        assert score == 0.0
        assert incertain is True

    def test_un_candidat_score_max(self):
        candidats = [
            {
                "nom_complet": "HOTEL LE SUD",
                "siege": {"code_postal": "34000", "libelle_commune": "Montpellier"},
                "etat_administratif": "A",
                "nature_juridique": "5710",
                "siren": "401111111",
            }
        ]
        result, score, incertain = selectionner_meilleur_candidat(
            candidats, "Hôtel Le Sud", "34000", "Montpellier"
        )
        assert result is not None
        assert result["siren"] == "401111111"
        assert score >= SEUIL_CONFIANCE
        assert incertain is False

    def test_choisit_le_plus_haut(self):
        candidats = [
            # Mauvais : autre dpt, pas actif
            {
                "nom_complet": "HOTEL LE SUD PARIS",
                "siege": {"code_postal": "75001"},
                "etat_administratif": "C",
                "nature_juridique": "5710",
                "siren": "999999999",
            },
            # Bon : tout matche
            {
                "nom_complet": "HOTEL LE SUD",
                "siege": {"code_postal": "34000", "libelle_commune": "Montpellier"},
                "etat_administratif": "A",
                "nature_juridique": "5710",
                "siren": "401111111",
            },
        ]
        result, _, _ = selectionner_meilleur_candidat(
            candidats, "Hôtel Le Sud", "34000", "Montpellier"
        )
        assert result is not None
        assert result["siren"] == "401111111"


class TestDetectionChaines:
    def test_ibis(self):
        est, groupe = detecter_chaine("Hôtel Ibis Marseille Est")
        assert est is True
        assert "Accor" in groupe

    def test_carrefour(self):
        est, groupe = detecter_chaine("Carrefour Market Béziers")
        assert est is True
        assert "Carrefour" in groupe

    def test_pas_chaine(self):
        est, groupe = detecter_chaine("Hôtel Le Sud")
        assert est is False
        assert groupe is None

    def test_nom_vide(self):
        est, groupe = detecter_chaine("")
        assert est is False
