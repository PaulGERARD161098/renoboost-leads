"""Tests du chargement et de la validation des verticales."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from renoboost_leads.verticale import (
    Verticale,
    VerticaleHorsV0Error,
    list_verticales,
    load_verticale,
)

SLUGS_ATTENDUS = {
    "irve-flottes-b2b",
    "ombrieres-parkings-grandes-surfaces",
    "rossini",
    "solaire-pme-toitures",
}


def _verticale_minimale(slug: str = "test-vert") -> dict:
    return {
        "verticale": {"slug": slug, "nom": "Test", "description": "desc"},
        "cible": {"type": "b2b", "detail": "PME test"},
        "offre": {
            "produit": "produit",
            "argument_principal": "argument",
            "ticket_moyen_eur": 1000,
        },
        "cibles": {
            "secteurs_places": [{"type": "establishment", "query": "q"}],
        },
        "signaux": ["signal 1"],
        "qualification": {"seuil_score_top": 70, "criteres_top": ["critere 1"]},
        "ton_mail": {
            "registre": "pro",
            "longueur_mots": 100,
            "attaque": "a",
            "cta": "c",
        },
        "sequence": {"j0": {"template": "t.md", "sujet": "s"}},
        "budget_typique": {
            "volume_cible": 100,
            "cout_pipeline_eur": 10,
            "cout_avec_l3_5_eur": 20,
        },
    }


def _ecrire(base: Path, slug: str, data: dict) -> Path:
    d = base / slug
    d.mkdir(parents=True)
    (d / "verticale.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return base


# ─── verticales réelles ───


def test_list_verticales_retourne_toutes() -> None:
    assert set(list_verticales()) == SLUGS_ATTENDUS


def test_charge_toutes_les_verticales_reelles() -> None:
    for slug in SLUGS_ATTENDUS:
        v = load_verticale(slug)
        assert isinstance(v, Verticale)
        assert v.slug == slug
        assert v.cible.type == "b2b"
        assert len(v.signaux) >= 1
        assert v.qualification.seuil_score_top == 70


# ─── validations ───


def test_signaux_vide_rejete(tmp_path: Path) -> None:
    data = _verticale_minimale()
    data["signaux"] = []
    base = _ecrire(tmp_path, "test-vert", data)
    with pytest.raises(ValidationError):
        load_verticale("test-vert", base_dir=base)


def test_qualification_absente_rejetee(tmp_path: Path) -> None:
    data = _verticale_minimale()
    del data["qualification"]
    base = _ecrire(tmp_path, "test-vert", data)
    with pytest.raises(ValidationError):
        load_verticale("test-vert", base_dir=base)


def test_champ_inconnu_rejete(tmp_path: Path) -> None:
    data = _verticale_minimale()
    data["champ_imprevu"] = 42
    base = _ecrire(tmp_path, "test-vert", data)
    with pytest.raises(ValidationError):
        load_verticale("test-vert", base_dir=base)


def test_cible_b2c_rejetee_en_v0(tmp_path: Path) -> None:
    data = _verticale_minimale("vert-b2c")
    data["cible"]["type"] = "b2c-particulier"
    base = _ecrire(tmp_path, "vert-b2c", data)
    with pytest.raises(VerticaleHorsV0Error):
        load_verticale("vert-b2c", base_dir=base)


def test_slug_incoherent_rejete(tmp_path: Path) -> None:
    data = _verticale_minimale("autre-slug")
    base = _ecrire(tmp_path, "dossier-slug", data)
    with pytest.raises(ValueError, match="Incohérence slug"):
        load_verticale("dossier-slug", base_dir=base)


def test_introuvable_leve(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_verticale("inexistante", base_dir=tmp_path)


def test_list_dossier_absent_renvoie_vide(tmp_path: Path) -> None:
    assert list_verticales(base_dir=tmp_path / "nexiste-pas") == []
