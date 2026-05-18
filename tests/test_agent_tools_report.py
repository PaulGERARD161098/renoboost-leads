"""Tests de l'outil generate_report (rapport HTML autonome)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from renoboost_leads.agent.tools import report as rep
from renoboost_leads.agent.tools import sessions as sess


@pytest.fixture
def fake_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "output"
    root.mkdir()
    monkeypatch.setattr(sess, "OUTPUT_ROOT", root)
    monkeypatch.setattr(rep, "OUTPUT_ROOT", root)
    return root


def _ecrire_csv(p: Path, rows: list[dict]) -> None:
    if not rows:
        p.write_text("nom\n", encoding="utf-8")
        return
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _session_l3(root: Path, sid: str, n: int = 5, complet: bool = True) -> Path:
    d = root / sid
    d.mkdir()
    rows = [
        {
            "nom": f"Entreprise {i}",
            "ville": "Lille",
            "siren": f"100{i:03d}" if complet else "",
            "dirigeant_nom": f"Martin{i}" if complet else "",
            "email_principal": f"contact{i}@ex.fr" if complet else "",
            "telephone": f"03 20 00 00 0{i}",
            "site_web": f"https://ex{i}.fr",
            "tranche_effectif": "11",
        }
        for i in range(n)
    ]
    _ecrire_csv(d / "etage3_contacts.csv", rows)
    (d / "run_stats.json").write_text(
        json.dumps(
            {"campaign": "test-pilote", "debut": "2026-05-18", "fin": "2026-05-18"}
        ),
        encoding="utf-8",
    )
    return d


def test_session_inconnue(fake_root: Path) -> None:
    res = rep.generate_report("nope")
    assert "error" in res


def test_l3_absent(fake_root: Path) -> None:
    (fake_root / "s1").mkdir()
    res = rep.generate_report("s1")
    assert "error" in res
    assert "etage3" in res["error"]


def test_genere_html_complet(fake_root: Path) -> None:
    _session_l3(fake_root, "s1", n=10, complet=True)
    res = rep.generate_report("s1")
    assert "error" not in res
    assert res["leads_inclus"] == 10
    assert res["verdict_go_phase2"] is True
    assert res["bytes_written"] > 1000
    # Fichier écrit
    p = fake_root / "s1" / "rapport.html"
    assert p.exists()
    html = p.read_text(encoding="utf-8")
    # Sections clés présentes
    assert "<!DOCTYPE html>" in html
    assert "RénoBoost" in html
    assert "test-pilote" in html
    assert "Entreprise 0" in html
    assert "Martin0" in html
    assert "contact0@ex.fr" in html
    # GO car tous champs remplis → SIREN/dirigeant/email à 100%
    assert "GO Phase 2" in html


def test_verdict_nogo_si_donnees_vides(fake_root: Path) -> None:
    _session_l3(fake_root, "s2", n=10, complet=False)
    res = rep.generate_report("s2")
    assert res["verdict_go_phase2"] is False
    html = (fake_root / "s2" / "rapport.html").read_text(encoding="utf-8")
    assert "NO-GO Phase 2" in html


def test_max_leads_tronque(fake_root: Path) -> None:
    _session_l3(fake_root, "s3", n=20)
    res = rep.generate_report("s3", max_leads=5)
    assert res["leads_inclus"] == 5
    html = (fake_root / "s3" / "rapport.html").read_text(encoding="utf-8")
    assert "Entreprise 4" in html
    assert "Entreprise 5" not in html


def test_output_path_personnalise(fake_root: Path, tmp_path: Path) -> None:
    _session_l3(fake_root, "s4", n=3)
    cible = tmp_path / "ailleurs" / "monrapport.html"
    res = rep.generate_report("s4", output_path=str(cible))
    assert "error" not in res
    assert cible.exists()
    assert "RénoBoost" in cible.read_text(encoding="utf-8")


def test_inclut_l3_5_si_present(fake_root: Path) -> None:
    d = _session_l3(fake_root, "s5", n=5)
    rows35 = [
        {"nom": f"E{i}", "email_verifie": f"v{i}@x.fr", "tel_direct": "0600000000"}
        for i in range(5)
    ]
    _ecrire_csv(d / "etage3_5_enrichment.csv", rows35)
    res = rep.generate_report("s5")
    assert "error" not in res
    html = (d / "rapport.html").read_text(encoding="utf-8")
    assert "Dropcontact" in html
    assert "L3.5" in html


def test_schema_et_dispatch_exposes() -> None:
    assert any(s["name"] == "generate_report" for s in rep.SCHEMAS)
    assert "generate_report" in rep.DISPATCH
    schema = rep.SCHEMAS[0]
    assert "session_id" in schema["input_schema"]["required"]


def test_outil_enregistre_dans_registry() -> None:
    """generate_report doit apparaître dans le registry global de l'agent."""
    from renoboost_leads.agent.tools import all_dispatch, all_schemas

    schemas = all_schemas()
    assert any(s["name"] == "generate_report" for s in schemas)
    assert "generate_report" in all_dispatch()
