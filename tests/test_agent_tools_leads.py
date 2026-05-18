"""Tests de l'outil prioritize_leads."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from renoboost_leads.agent.tools import leads as ld
from renoboost_leads.agent.tools import sessions as sess


@pytest.fixture
def fake_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "output"
    root.mkdir()
    monkeypatch.setattr(sess, "OUTPUT_ROOT", root)
    monkeypatch.setattr(ld, "OUTPUT_ROOT", root)
    return root


def _ecrire(p: Path, rows: list[dict]) -> None:
    fieldnames = sorted({k for r in rows for k in r.keys()})
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def test_session_inconnue(fake_root: Path) -> None:
    res = ld.prioritize_leads("nope")
    assert "error" in res


def test_aucun_csv(fake_root: Path) -> None:
    (fake_root / "vide").mkdir()
    res = ld.prioritize_leads("vide")
    assert "error" in res
    assert "exploitable" in res["error"]


def test_priorite_l3_seul(fake_root: Path) -> None:
    d = fake_root / "s1"
    d.mkdir()
    rows = [
        {
            "nom": "A",
            "email_principal": "a@x.fr",
            "telephone": "0102",
            "dirigeant_nom": "X",
        },
        {"nom": "B"},  # rien
        {"nom": "C", "email_principal": "c@x.fr"},
    ]
    _ecrire(d / "etage3_contacts.csv", rows)
    res = ld.prioritize_leads("s1", top_n=10)
    assert res["total"] == 3
    assert res["source"] == "etage3_contacts.csv"
    # A : 50+20+20=90 → tiède
    # C : 50 → froid
    # B : 0 → froid
    noms = [t["nom"] for t in res["top"]]
    assert noms[0] == "A"
    assert noms[-1] == "B"
    assert res["distribution"]["tiede"] == 1
    assert res["distribution"]["froid"] == 2


def test_priorite_l4_score_claude(fake_root: Path) -> None:
    d = fake_root / "s2"
    d.mkdir()
    rows = [
        {
            "nom": "Top",
            "email_dropcontact": "t@x.fr",
            "telephone_direct_dropcontact": "0606",
            "nom_dirigeant_dropcontact": "Dupont",
            "score_interet": "80",
        },  # 50+20+20+80=170 → chaud
        {"nom": "Petit", "score_interet": "10"},  # 10 → froid
    ]
    _ecrire(d / "etage4_prospection.csv", rows)
    res = ld.prioritize_leads("s2")
    assert res["source"] == "etage4_prospection.csv"
    assert res["top"][0]["bucket"] == "chaud"
    assert res["top"][0]["score_combine"] == pytest.approx(170.0)
    assert res["distribution"]["chaud"] == 1
    assert res["distribution"]["froid"] == 1


def test_priorite_priorise_l4_sur_l3(fake_root: Path) -> None:
    d = fake_root / "s3"
    d.mkdir()
    _ecrire(d / "etage3_contacts.csv", [{"nom": "L3"}])
    _ecrire(d / "etage4_prospection.csv", [{"nom": "L4"}])
    res = ld.prioritize_leads("s3")
    assert res["source"] == "etage4_prospection.csv"
    assert res["top"][0]["nom"] == "L4"


def test_score_invalide_ignore(fake_root: Path) -> None:
    d = fake_root / "s4"
    d.mkdir()
    rows = [{"nom": "A", "score_interet": "abc"}]
    _ecrire(d / "etage4_prospection.csv", rows)
    res = ld.prioritize_leads("s4")
    assert res["top"][0]["score_combine"] == 0.0
