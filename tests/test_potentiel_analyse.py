"""Tests de l'orchestrateur d'analyse (combinaison Vision + IRVE + IGN)."""

from __future__ import annotations

from renoboost_leads.potentiel.analyse import analyser_potentiels
from renoboost_leads.potentiel.irve import Borne, ClientIRVE

_LAT, _LON = 50.6292, 3.0573


def _vision(**over):
    base = {
        "toiture": {"presente": True, "type": "plate", "surface_estimee_m2": 1200},
        "parking": {"present": True, "surface_estimee_m2": 2500, "nb_places_estime": 100,
                    "partage": False},
        "bornes_visibles": 0,
    }
    base.update(over)
    return base


def test_analyse_complete_3_scores():
    irve = ClientIRVE(bornes=[Borne(_LAT + 0.005, _LON, 22.0)])  # 1 borne ~550 m
    a = analyser_potentiels(
        latitude=_LAT, longitude=_LON, vision=_vision(),
        irve=irve, surface_batie_m2=1500, exploitant_probable="ACME SAS",
    )
    # Solaire : IGN 1500 m² × ratio plate 0.7 = 1050 → palier 7, +2 plate = 9
    assert a.solaire.score == 9
    assert a.solaire.surface_toiture_m2 == 1500
    # Ombrières : 100 places dédié → 7 + 2 = 9
    assert a.ombrieres.score == 9
    assert a.ombrieres.exploitant_probable == "ACME SAS"
    # Bornes : voisin 1 (≤1km) → adoption 3 + rayon 2 = 5, + manque 4 = 9
    assert a.bornes.score == 9
    assert a.version == 2
    assert a.meilleur in ("solaire", "ombrieres", "bornes")


def test_surface_ign_prioritaire_sur_vision():
    a = analyser_potentiels(
        latitude=_LAT, longitude=_LON,
        vision=_vision(toiture={"presente": True, "type": "plate", "surface_estimee_m2": 300}),
        surface_batie_m2=2000,
    )
    assert a.solaire.surface_toiture_m2 == 2000  # IGN prime sur l'estimation Vision


def test_sans_irve_compte_zero_mais_signaux_ve():
    a = analyser_potentiels(
        latitude=_LAT, longitude=_LON, vision=_vision(bornes_visibles=0),
        irve=None, signaux_ve=True,
    )
    # Pas de données IRVE → adoption via signaux VE (3) + manque sur site (4) = 7
    assert a.bornes.score == 7
    assert a.bornes.rayon_10km == 0


def test_bornes_vues_par_vision_completent_irve():
    a = analyser_potentiels(
        latitude=_LAT, longitude=_LON, vision=_vision(bornes_visibles=2), irve=None,
    )
    assert a.bornes.sur_site == 2  # IRVE vide mais Vision en voit 2


def test_pas_de_toiture_ni_parking():
    a = analyser_potentiels(
        latitude=_LAT, longitude=_LON,
        vision={"toiture": {"presente": False}, "parking": {"present": False}},
    )
    assert a.solaire.score == 0
    assert a.ombrieres.score == 0
