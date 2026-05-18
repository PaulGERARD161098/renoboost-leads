"""Tests de l'outil diagnose_quality."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from renoboost_leads.agent.tools import quality as q
from renoboost_leads.agent.tools import sessions as sess


@pytest.fixture
def fake_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "output"
    root.mkdir()
    monkeypatch.setattr(sess, "OUTPUT_ROOT", root)
    monkeypatch.setattr(q, "OUTPUT_ROOT", root)
    return root


def _ecrire_csv(p: Path, rows: list[dict]) -> None:
    if not rows:
        p.write_text("nom\n", encoding="utf-8")
        return
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def test_session_inconnue(fake_root: Path) -> None:
    res = q.diagnose_quality("nope")
    assert "error" in res


def test_l3_absent(fake_root: Path) -> None:
    (fake_root / "s1").mkdir()
    res = q.diagnose_quality("s1")
    assert "error" in res
    assert "etage3" in res["error"]


def test_l3_metriques_tous_pleins(fake_root: Path) -> None:
    d = fake_root / "s1"
    d.mkdir()
    rows = [
        {
            "nom": f"E{i}",
            "siren": f"100{i}",
            "dirigeant_nom": f"Dupont{i}",
            "email_principal": f"e{i}@x.fr",
            "site_web": f"https://x{i}.fr",
            "tranche_effectif": "11",
            "naf": "69.10Z",
        }
        for i in range(10)
    ]
    _ecrire_csv(d / "etage3_contacts.csv", rows)
    res = q.diagnose_quality("s1")
    assert res["metriques_l3"]["row_count"] == 10
    assert res["metriques_l3"]["pct_siren_matche"] == 100.0
    assert res["metriques_l3"]["pct_dirigeant_identifie"] == 100.0
    assert res["metriques_l3"]["pct_email_scrape"] == 100.0
    assert res["verdict_pilote_phase1"]["go_phase2"] is True


def test_l3_metriques_partiels(fake_root: Path) -> None:
    d = fake_root / "s2"
    d.mkdir()
    rows = [
        {"nom": "A", "siren": "100", "dirigeant_nom": "X", "email_principal": "a@x.fr"},
        {"nom": "B", "siren": "200", "dirigeant_nom": "Y", "email_principal": ""},
        {"nom": "C", "siren": "", "dirigeant_nom": "", "email_principal": ""},
        {"nom": "D", "siren": "400", "dirigeant_nom": "", "email_principal": "d@x.fr"},
    ]
    _ecrire_csv(d / "etage3_contacts.csv", rows)
    res = q.diagnose_quality("s2")
    m = res["metriques_l3"]
    assert m["pct_siren_matche"] == 75.0
    assert m["pct_dirigeant_identifie"] == 50.0
    assert m["pct_email_scrape"] == 50.0


def test_verdict_phase1_no_go(fake_root: Path) -> None:
    d = fake_root / "s3"
    d.mkdir()
    rows = [{"nom": f"E{i}", "siren": "" if i > 1 else "100"} for i in range(10)]
    _ecrire_csv(d / "etage3_contacts.csv", rows)
    res = q.diagnose_quality("s3")
    assert res["verdict_pilote_phase1"]["go_phase2"] is False
    # Au moins le critère SIREN est faux
    siren_critere = next(
        c for c in res["verdict_pilote_phase1"]["criteres"] if "SIREN" in c["critere"]
    )
    assert siren_critere["ok"] is False


def test_l3_5_present(fake_root: Path) -> None:
    d = fake_root / "s4"
    d.mkdir()
    _ecrire_csv(
        d / "etage3_contacts.csv",
        [{"nom": "A", "siren": "100", "dirigeant_nom": "X", "email_principal": "a@x.fr"}],
    )
    _ecrire_csv(
        d / "etage3_5_enrichment.csv",
        [
            {"nom": "A", "email_verifie": "a@x.fr", "tel_direct": "0102030405"},
            {"nom": "B", "email_verifie": "", "tel_direct": ""},
        ],
    )
    res = q.diagnose_quality("s4")
    assert res["metriques_l3_5"]["row_count_3_5"] == 2
    assert res["metriques_l3_5"]["pct_email_verifie_dropcontact"] == 50.0


def test_anomalies_echantillon(fake_root: Path) -> None:
    d = fake_root / "s5"
    d.mkdir()
    rows = [
        {
            "nom": "Bon",
            "ville": "B",
            "siren": "100",
            "dirigeant_nom": "X",
            "email_principal": "a@x.fr",
        },
        {"nom": "Vide1", "ville": "V1", "siren": "", "dirigeant_nom": "", "email_principal": ""},
        {"nom": "Vide2", "ville": "V2", "siren": "", "dirigeant_nom": "", "email_principal": ""},
    ]
    _ecrire_csv(d / "etage3_contacts.csv", rows)
    res = q.diagnose_quality("s5")
    assert len(res["anomalies_echantillon"]) == 2
    noms_anomalies = [a["nom"] for a in res["anomalies_echantillon"]]
    assert "Bon" not in noms_anomalies
