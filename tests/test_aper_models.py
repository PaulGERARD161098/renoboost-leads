"""Tests modèles + logique réglementaire parkings APER."""

from __future__ import annotations

from renoboost_leads.parkings_aper.models import (
    ECHEANCE_GROS,
    ECHEANCE_STANDARD,
    SEUIL_APER_M2,
    SEUIL_GROS_PARKING_M2,
    LigneParking,
    echeance_pour_surface,
)


class TestEcheance:
    def test_gros_parking_echeance_2026_priorite_haute(self):
        ech, prio = echeance_pour_surface(SEUIL_GROS_PARKING_M2)
        assert ech == ECHEANCE_GROS
        assert prio == "haute"

    def test_parking_standard_echeance_2028(self):
        ech, prio = echeance_pour_surface(2000)
        assert ech == ECHEANCE_STANDARD
        assert prio == "standard"

    def test_seuil_exact_gros_est_haute(self):
        _, prio = echeance_pour_surface(10000)
        assert prio == "haute"


class TestLigneParking:
    def test_surface_ombrable_50pct(self):
        lp = LigneParking(surface_m2=2000)
        assert lp.surface_ombrable_m2 == 1000.0

    def test_nb_places_estime(self):
        lp = LigneParking(surface_m2=2500)
        assert lp.nb_places_estime == 100  # 2500 / 25

    def test_siren_depuis_siret(self):
        lp = LigneParking(surface_m2=1600, siren="40211111100025")
        assert lp.siren == "402111111"

    def test_siren_invalide_devient_none(self):
        lp = LigneParking(surface_m2=1600, siren="123")
        assert lp.siren is None

    def test_code_postal_padding(self):
        lp = LigneParking(surface_m2=1600, code_postal="6300")
        assert lp.code_postal == "06300"

    def test_identifiant_stable_priorite_id(self):
        lp = LigneParking(surface_m2=1600, identifiant="osm-42", siren="402111111")
        assert lp.identifiant_stable() == "id:osm-42"

    def test_identifiant_stable_fallback_siren(self):
        lp = LigneParking(surface_m2=1600, siren="402111111")
        assert lp.identifiant_stable() == "siren:402111111"

    def test_identifiant_stable_fallback_nom_cp(self):
        lp = LigneParking(surface_m2=1600, nom="Carrefour Lens", code_postal="62300")
        assert lp.identifiant_stable() == "nomcp:carrefour lens|62300"

    def test_seuil_aper_constant(self):
        assert SEUIL_APER_M2 == 1500.0
