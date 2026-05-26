"""Tests des outils agent campagnes (déterministes, sans appel API)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from renoboost_leads.agent.tools import campagnes as ct
from renoboost_leads.campagne import load_campagne


def _verticale_min(slug: str, cible: str = "b2b") -> dict:
    return {
        "verticale": {"slug": slug, "nom": "Test", "description": "desc"},
        "cible": {"type": cible, "detail": "PME test"},
        "offre": {"produit": "p", "argument_principal": "a", "ticket_moyen_eur": 1000},
        "cibles": {"secteurs_places": [{"type": "establishment", "query": "q"}]},
        "signaux": ["signal"],
        "qualification": {"seuil_score_top": 70, "criteres_top": ["c1"]},
        "ton_mail": {"registre": "pro", "longueur_mots": 100, "attaque": "a", "cta": "c"},
        "sequence": {"j0": {"template": "t", "sujet": "s"}},
        "budget_typique": {"volume_cible": 100, "cout_pipeline_eur": 10, "cout_avec_l3_5_eur": 20},
    }


@pytest.fixture(autouse=True)
def _isoler(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Path]:
    camp = tmp_path / "campagnes"
    vert = tmp_path / "verticales"
    camp.mkdir()
    vert.mkdir()
    # verticales d'appui
    for slug, cible in [("vert-test", "b2b"), ("vert-b2c", "b2c-particulier")]:
        d = vert / slug
        d.mkdir()
        (d / "verticale.yaml").write_text(
            yaml.safe_dump(_verticale_min(slug, cible), allow_unicode=True), encoding="utf-8"
        )
    monkeypatch.setattr(ct, "CAMPAGNES_ROOT", camp)
    monkeypatch.setattr(ct, "VERTICALES_ROOT", vert)
    return {"camp": camp, "vert": vert}


def _args(cid: str = "camp-test", slug: str = "vert-test") -> dict:
    return {
        "id": cid,
        "verticale_slug": slug,
        "zone": {"type": "departement", "codes": ["59", "80"]},
        "volume": {"cible": 150},
        "budget": {"max_eur": 20.0},
        "nom": "Pilote",
    }


def test_create_valide_ecrit_et_recharge(_isoler: dict[str, Path]) -> None:
    res = ct.create_campagne_tool(**_args())
    assert res.get("ok") is True
    assert res["config_preview"]["seuil_top_lead"] == 70
    c = load_campagne("camp-test", base_dir=_isoler["camp"])
    assert c.verticale_slug == "vert-test"
    assert c.zone.codes == ["59", "80"]


def test_create_verticale_inexistante(_isoler: dict[str, Path]) -> None:
    res = ct.create_campagne_tool(**_args(slug="fantome"))
    assert "error" in res
    assert not (_isoler["camp"] / "camp-test").exists()


def test_create_verticale_b2c_refuse(_isoler: dict[str, Path]) -> None:
    res = ct.create_campagne_tool(**_args(slug="vert-b2c"))
    assert "error" in res
    assert not (_isoler["camp"] / "camp-test").exists()


def test_create_zone_vide_invalide(_isoler: dict[str, Path]) -> None:
    args = _args()
    args["zone"] = {"type": "departement", "codes": []}
    res = ct.create_campagne_tool(**args)
    assert "error" in res
    assert "details" in res
    assert not (_isoler["camp"] / "camp-test").exists()


def test_create_id_traversal_refuse(_isoler: dict[str, Path]) -> None:
    res = ct.create_campagne_tool(**_args(cid="../evil"))
    assert "error" in res
    assert not (_isoler["camp"].parent / "evil").exists()


def test_create_refuse_ecrasement(_isoler: dict[str, Path]) -> None:
    assert ct.create_campagne_tool(**_args()).get("ok")
    res = ct.create_campagne_tool(**_args())
    assert "error" in res
    assert "existe déjà" in res["error"]


def test_get_campagne(_isoler: dict[str, Path]) -> None:
    assert "error" in ct.get_campagne_tool("camp-test")
    ct.create_campagne_tool(**_args())
    res = ct.get_campagne_tool("camp-test")
    assert res["id"] == "camp-test"
    assert res["config_preview"]["nb_secteurs"] == 1


def test_list_campagnes(_isoler: dict[str, Path]) -> None:
    ct.create_campagne_tool(**_args("camp-a"))
    ct.create_campagne_tool(**_args("camp-b"))
    res = ct.list_campagnes_tool()
    assert res["total"] == 2
    assert {i["id"] for i in res["campagnes"]} == {"camp-a", "camp-b"}


def test_schemas_et_dispatch_coherents() -> None:
    for s in ct.SCHEMAS:
        assert "name" in s and "input_schema" in s
        assert s["name"] in ct.DISPATCH
    assert set(ct.DISPATCH) == {s["name"] for s in ct.SCHEMAS}
