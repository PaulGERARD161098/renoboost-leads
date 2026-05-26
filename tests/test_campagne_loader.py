"""Tests du chargement, de la validation et de la sauvegarde des campagnes."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from renoboost_leads.campagne import Campagne, list_campagnes, load_campagne, save_campagne
from renoboost_leads.verticale import VerticaleHorsV0Error


def _verticale_min(slug: str = "vert-test", cible: str = "b2b") -> dict:
    return {
        "verticale": {"slug": slug, "nom": "Test", "description": "desc"},
        "cible": {"type": cible, "detail": "PME test"},
        "offre": {"produit": "p", "argument_principal": "a", "ticket_moyen_eur": 1000},
        "cibles": {"secteurs_places": [{"type": "establishment", "query": "q"}]},
        "signaux": ["signal 1"],
        "qualification": {"seuil_score_top": 70, "criteres_top": ["c1"]},
        "ton_mail": {"registre": "pro", "longueur_mots": 100, "attaque": "a", "cta": "c"},
        "sequence": {"j0": {"template": "t", "sujet": "s"}},
        "budget_typique": {"volume_cible": 100, "cout_pipeline_eur": 10, "cout_avec_l3_5_eur": 20},
    }


def _ecrire_verticale(base: Path, slug: str = "vert-test", cible: str = "b2b") -> Path:
    d = base / slug
    d.mkdir(parents=True)
    (d / "verticale.yaml").write_text(
        yaml.safe_dump(_verticale_min(slug, cible), allow_unicode=True), encoding="utf-8"
    )
    return base


def _campagne_dict(cid: str = "camp-test", slug: str = "vert-test") -> dict:
    return {
        "campagne": {"id": cid, "verticale_slug": slug},
        "zone": {"type": "departement", "codes": ["59", "80"]},
        "volume": {"cible": 150},
        "budget": {"max_eur": 20.0},
    }


def _ecrire_campagne(base: Path, cid: str, data: dict) -> Path:
    d = base / cid
    d.mkdir(parents=True)
    (d / "campagne.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return base


# ─── chargement / validation ───


def test_load_campagne_valide(tmp_path: Path) -> None:
    base = _ecrire_campagne(tmp_path, "camp-test", _campagne_dict())
    c = load_campagne("camp-test", base_dir=base)
    assert isinstance(c, Campagne)
    assert c.id == "camp-test"
    assert c.verticale_slug == "vert-test"
    assert c.zone.codes == ["59", "80"]
    assert c.volume.cible == 150


def test_load_introuvable(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_campagne("absente", base_dir=tmp_path)


def test_id_incoherent_rejete(tmp_path: Path) -> None:
    base = _ecrire_campagne(tmp_path, "dossier-x", _campagne_dict(cid="autre-id"))
    with pytest.raises(ValueError, match="Incohérence id"):
        load_campagne("dossier-x", base_dir=base)


def test_champ_inconnu_rejete(tmp_path: Path) -> None:
    data = _campagne_dict()
    data["imprevu"] = 42
    base = _ecrire_campagne(tmp_path, "camp-test", data)
    with pytest.raises(ValidationError):
        load_campagne("camp-test", base_dir=base)


def test_id_majuscule_rejete(tmp_path: Path) -> None:
    data = _campagne_dict(cid="Camp-Test")
    base = _ecrire_campagne(tmp_path, "Camp-Test", data)
    with pytest.raises(ValidationError):
        load_campagne("Camp-Test", base_dir=base)


def test_list_campagnes(tmp_path: Path) -> None:
    assert list_campagnes(base_dir=tmp_path) == []
    _ecrire_campagne(tmp_path, "b-camp", _campagne_dict("b-camp"))
    _ecrire_campagne(tmp_path, "a-camp", _campagne_dict("a-camp"))
    assert list_campagnes(base_dir=tmp_path) == ["a-camp", "b-camp"]


# ─── sauvegarde (vérifie la verticale référencée) ───


def test_save_ecrit_et_recharge(tmp_path: Path) -> None:
    vert_dir = _ecrire_verticale(tmp_path / "verticales")
    camp_dir = tmp_path / "campagnes"
    c = Campagne.model_validate(_campagne_dict("camp-test", "vert-test"))
    chemin = save_campagne(c, base_dir=camp_dir, verticales_dir=vert_dir)
    assert chemin.exists()
    rechargee = load_campagne("camp-test", base_dir=camp_dir)
    assert rechargee.verticale_slug == "vert-test"


def test_save_refuse_verticale_inexistante(tmp_path: Path) -> None:
    vert_dir = tmp_path / "verticales"
    vert_dir.mkdir()
    camp_dir = tmp_path / "campagnes"
    c = Campagne.model_validate(_campagne_dict("camp-test", "fantome"))
    with pytest.raises(FileNotFoundError):
        save_campagne(c, base_dir=camp_dir, verticales_dir=vert_dir)
    assert not (camp_dir / "camp-test").exists()


def test_save_refuse_verticale_b2c(tmp_path: Path) -> None:
    vert_dir = _ecrire_verticale(tmp_path / "verticales", "vert-b2c", cible="b2c-particulier")
    camp_dir = tmp_path / "campagnes"
    c = Campagne.model_validate(_campagne_dict("camp-test", "vert-b2c"))
    with pytest.raises(VerticaleHorsV0Error):
        save_campagne(c, base_dir=camp_dir, verticales_dir=vert_dir)
    assert not (camp_dir / "camp-test").exists()
