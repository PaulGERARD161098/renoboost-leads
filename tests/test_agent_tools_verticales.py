"""Tests des outils agent verticales (déterministes, sans appel API)."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from renoboost_leads.agent.tools import verticales as vt
from renoboost_leads.verticale import load_verticale


@pytest.fixture(autouse=True)
def _isoler_verticales(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    racine = tmp_path / "verticales"
    racine.mkdir()
    monkeypatch.setattr(vt, "VERTICALES_ROOT", racine)
    return racine


def _valide(slug: str = "clim-pro-b2b") -> dict:
    return {
        "verticale": {"slug": slug, "nom": "Clim pro", "description": "desc"},
        "cible": {"type": "b2b", "detail": "PME tertiaires"},
        "offre": {
            "produit": "climatisation réversible",
            "argument_principal": "confort + économies",
            "ticket_moyen_eur": 15000,
        },
        "cibles": {"secteurs_places": [{"type": "establishment", "query": "bureaux"}]},
        "signaux": ["bâtiment tertiaire récent"],
        "qualification": {"seuil_score_top": 70, "criteres_top": ["décideur trouvé"]},
        "ton_mail": {
            "registre": "pro",
            "longueur_mots": 110,
            "attaque": "a",
            "cta": "c",
        },
        "sequence": {"j0": {"template": "t.md", "sujet": "s"}},
        "budget_typique": {
            "volume_cible": 100,
            "cout_pipeline_eur": 12,
            "cout_avec_l3_5_eur": 30,
        },
    }


def test_create_valide_ecrit_et_recharge(_isoler_verticales: Path) -> None:
    res = vt.create_verticale_tool("clim-pro-b2b", _valide())
    assert res.get("ok") is True
    v = load_verticale("clim-pro-b2b", base_dir=_isoler_verticales)
    assert v.verticale.nom == "Clim pro"
    assert v.cible.type == "b2b"


def test_create_invalide_ne_rien_ecrire(_isoler_verticales: Path) -> None:
    data = _valide()
    data["signaux"] = []
    res = vt.create_verticale_tool("clim-pro-b2b", data)
    assert "error" in res
    assert "details" in res
    assert not (_isoler_verticales / "clim-pro-b2b").exists()


def test_create_b2c_refuse(_isoler_verticales: Path) -> None:
    data = _valide("clim-b2c")
    data["cible"]["type"] = "b2c-particulier"
    res = vt.create_verticale_tool("clim-b2c", data)
    assert "error" in res
    assert not (_isoler_verticales / "clim-b2c").exists()


def test_create_refuse_ecrasement(_isoler_verticales: Path) -> None:
    assert vt.create_verticale_tool("clim-pro-b2b", _valide()).get("ok")
    res = vt.create_verticale_tool("clim-pro-b2b", _valide())
    assert "error" in res
    assert "existe déjà" in res["error"]


def test_create_slug_incoherent(_isoler_verticales: Path) -> None:
    data = _valide("autre")
    res = vt.create_verticale_tool("clim-pro-b2b", data)
    assert "error" in res
    assert "incohérence" in res["error"].lower()


def test_create_traversal_refuse(_isoler_verticales: Path) -> None:
    res = vt.create_verticale_tool("../evil", _valide())
    assert "error" in res
    assert not (_isoler_verticales.parent / "evil").exists()


def test_refine_exige_existant(_isoler_verticales: Path) -> None:
    res = vt.refine_verticale_tool("clim-pro-b2b", _valide())
    assert "error" in res
    assert "n'existe pas" in res["error"]


def test_refine_met_a_jour(_isoler_verticales: Path) -> None:
    vt.create_verticale_tool("clim-pro-b2b", _valide())
    data = copy.deepcopy(_valide())
    data["verticale"]["nom"] = "Clim pro v2"
    res = vt.refine_verticale_tool("clim-pro-b2b", data)
    assert res.get("ok") is True
    v = load_verticale("clim-pro-b2b", base_dir=_isoler_verticales)
    assert v.verticale.nom == "Clim pro v2"


def test_get_verticale(_isoler_verticales: Path) -> None:
    assert "error" in vt.get_verticale_tool("clim-pro-b2b")
    vt.create_verticale_tool("clim-pro-b2b", _valide())
    res = vt.get_verticale_tool("clim-pro-b2b")
    assert res["slug"] == "clim-pro-b2b"
    assert res["verticale"]["cible"]["type"] == "b2b"


def test_list_verticales_tool(_isoler_verticales: Path) -> None:
    vt.create_verticale_tool("clim-pro-b2b", _valide("clim-pro-b2b"))
    vt.create_verticale_tool("clim-indus-b2b", _valide("clim-indus-b2b"))
    res = vt.list_verticales_tool()
    assert res["total"] == 2
    slugs = {item["slug"] for item in res["verticales"]}
    assert slugs == {"clim-pro-b2b", "clim-indus-b2b"}


def test_schemas_et_dispatch_coherents() -> None:
    for s in vt.SCHEMAS:
        assert "name" in s and "input_schema" in s
        assert s["name"] in vt.DISPATCH
    assert set(vt.DISPATCH) == {s["name"] for s in vt.SCHEMAS}
