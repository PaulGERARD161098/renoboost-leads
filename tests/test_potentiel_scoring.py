"""Tests du scoring /10 des 3 potentiels (logique pure, barèmes calibrés)."""

from __future__ import annotations

from renoboost_leads.potentiel.scoring import (
    scorer_bornes,
    scorer_ombrieres,
    scorer_solaire,
)


class TestSolaire:
    def test_grande_toiture_plate_max(self):
        p = scorer_solaire(surface_exploitable_m2=2000, type_toiture="plate")
        assert p.score == 10 and p.niveau == "Fort"

    def test_paliers(self):
        assert scorer_solaire(surface_exploitable_m2=1000).score == 7
        assert scorer_solaire(surface_exploitable_m2=500).score == 4
        assert scorer_solaire(surface_exploitable_m2=100).score == 1

    def test_bonus_plate_et_malus_nord(self):
        assert scorer_solaire(surface_exploitable_m2=500, type_toiture="plate").score == 6
        assert scorer_solaire(surface_exploitable_m2=500, type_toiture="inclinee_nord").score == 2

    def test_absente_zero(self):
        p = scorer_solaire(surface_exploitable_m2=0)
        assert p.score == 0 and p.niveau == "Nul"

    def test_clamp_haut(self):
        # 10 + bonus reste plafonné à 10
        assert scorer_solaire(surface_exploitable_m2=5000, type_toiture="plate").score == 10


class TestOmbrieres:
    def test_grand_parking_dedie_max(self):
        p = scorer_ombrieres(parking_present=True, nb_places=200, partage=False)
        assert p.score == 10

    def test_paliers(self):
        assert scorer_ombrieres(parking_present=True, nb_places=100).score == 7
        assert scorer_ombrieres(parking_present=True, nb_places=30).score == 4
        assert scorer_ombrieres(parking_present=True, nb_places=10).score == 1

    def test_malus_partage(self):
        # 7 (100 places) - 3 (partagé) = 4
        assert scorer_ombrieres(parking_present=True, nb_places=100, partage=True).score == 4

    def test_pas_de_parking_zero(self):
        assert scorer_ombrieres(parking_present=False, nb_places=None).score == 0


class TestBornes:
    def test_zone_electrifiee_sans_borne_top(self):
        # adoption 3 (voisins) + 3 (>=10 rayon) cap 6 + manque 4 = 10
        p = scorer_bornes(sur_site=0, voisinage_1km=2, rayon_10km=15)
        assert p.score == 10 and p.niveau == "Fort"

    def test_signaux_ve_comptent_comme_adoption(self):
        p = scorer_bornes(sur_site=0, voisinage_1km=0, rayon_10km=0, signaux_ve=True)
        assert p.score == 3 + 4  # adoption 3 + manque 4

    def test_deja_equipe_baisse(self):
        # adoption 3 (voisins) + 2 (rayon 1-9) = 5 ; déjà équipé manque=1 → 6
        p = scorer_bornes(sur_site=2, voisinage_1km=1, rayon_10km=3)
        assert p.score == 6

    def test_zone_vierge_isolee_faible(self):
        # aucune adoption, pas de borne sur site → 0 + 4 = 4
        p = scorer_bornes(sur_site=0, voisinage_1km=0, rayon_10km=0)
        assert p.score == 4

    def test_adoption_plafonnee_a_6(self):
        p = scorer_bornes(sur_site=0, voisinage_1km=5, rayon_10km=50, signaux_ve=True)
        assert p.score == 10  # 6 (cap) + 4
