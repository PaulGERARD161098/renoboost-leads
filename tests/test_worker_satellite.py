"""Test du flux d'analyse satellite worker (Vision mockée, zéro réseau)."""

from __future__ import annotations


def test_analyser_potentiel_renvoie_structure_v2(monkeypatch):
    import renoboost_leads.potentiel.ign as ign_mod
    import renoboost_leads.potentiel.irve as irve_mod
    import worker.satellite as sat
    from renoboost_leads.potentiel.irve import ComptageBornes

    vision = {
        "toiture": {"presente": True, "type": "plate", "surface_estimee_m2": 1000},
        "parking": {"present": True, "nb_places_estime": 80, "partage": False},
        "bornes_visibles": 0,
    }
    monkeypatch.setattr(sat, "_vision_observations", lambda *a, **k: (vision, "http://img"))
    monkeypatch.setattr(ign_mod, "surface_batie_m2", lambda lat, lon: 1500)

    class _FakeIRVE:
        def __init__(self, *a, **k):
            pass

        def compter(self, lat, lon):
            return ComptageBornes(sur_site=0, voisinage_1km=1, rayon_10km=3, types=["22 kW (AC)"])

    monkeypatch.setattr(irve_mod, "ClientIRVE", _FakeIRVE)

    res = sat.analyser_potentiel(50.63, 3.06, "key", exploitant="ACME SAS")
    assert res is not None
    assert res["version"] == 2
    # Solaire : 1500 × 0.7 = 1050 → 7, +2 plate = 9
    assert res["solaire"]["score"] == 9
    assert res["solaire"]["surface_toiture_m2"] == 1500
    # Ombrières : 80 places dédié → 7 + 2 = 9
    assert res["ombrieres"]["score"] == 9
    assert res["ombrieres"]["exploitant_probable"] == "ACME SAS"
    # Bornes : adoption (voisin 1 → 3) + rayon (3 → 2) = 5, manque 4 = 9
    assert res["bornes"]["score"] == 9
    assert res["image_url"] == "http://img"
    assert res["meilleur"] in ("solaire", "ombrieres", "bornes")


def test_analyser_potentiel_vision_indispo_renvoie_none(monkeypatch):
    import worker.satellite as sat

    monkeypatch.setattr(sat, "_vision_observations", lambda *a, **k: None)
    assert sat.analyser_potentiel(50.63, 3.06, "key") is None
