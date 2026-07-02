"""Tests des outils sessions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from renoboost_leads.agent.tools import sessions as sess


@pytest.fixture
def fake_output_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "output"
    root.mkdir()
    monkeypatch.setattr(sess, "OUTPUT_ROOT", root)
    return root


def _ecrire_csv(p: Path, rows: list[dict]) -> None:
    if not rows:
        p.write_text("col\n", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    lignes = [",".join(fieldnames)]
    for r in rows:
        lignes.append(",".join(str(r[k]) for k in fieldnames))
    p.write_text("\n".join(lignes) + "\n", encoding="utf-8")


def test_list_sessions_vide(fake_output_root: Path) -> None:
    res = sess.list_sessions()
    assert res == {"count": 0, "sessions": []}


def test_list_sessions_trie_recent_dabord(fake_output_root: Path) -> None:
    (fake_output_root / "20260101-100000-a").mkdir()
    (fake_output_root / "20260518-091234-b").mkdir()
    (fake_output_root / "20250601-080000-c").mkdir()
    res = sess.list_sessions()
    ids = [s["session_id"] for s in res["sessions"]]
    assert ids == ["20260518-091234-b", "20260101-100000-a", "20250601-080000-c"]


def test_list_sessions_detecte_stages(fake_output_root: Path) -> None:
    d = fake_output_root / "20260518-x"
    d.mkdir()
    _ecrire_csv(d / "etage1_decouverte.csv", [{"nom": "A"}])
    _ecrire_csv(d / "etage3_contacts.csv", [{"nom": "A"}])
    res = sess.list_sessions()
    stages = res["sessions"][0]["stages_disponibles"]
    assert "1" in stages
    assert "3" in stages
    assert "4" not in stages


def test_list_sessions_lit_run_stats(fake_output_root: Path) -> None:
    d = fake_output_root / "20260518-x"
    d.mkdir()
    (d / "run_stats.json").write_text(
        json.dumps({"campaign": "pilote59", "debut": "2026-05-18T09:00:00Z"}),
        encoding="utf-8",
    )
    res = sess.list_sessions()
    assert res["sessions"][0]["campaign"] == "pilote59"
    assert res["sessions"][0]["debut"] == "2026-05-18T09:00:00Z"


def test_list_sessions_run_stats_corrompu_ignore(fake_output_root: Path) -> None:
    d = fake_output_root / "20260518-x"
    d.mkdir()
    (d / "run_stats.json").write_text("{ pas du json", encoding="utf-8")
    res = sess.list_sessions()
    assert "campaign" not in res["sessions"][0]


def test_list_sessions_limit(fake_output_root: Path) -> None:
    for i in range(5):
        (fake_output_root / f"2026010{i}-x").mkdir()
    res = sess.list_sessions(limit=2)
    assert len(res["sessions"]) == 2


def test_read_session_inconnue(fake_output_root: Path) -> None:
    res = sess.read_session("fantome", stage="3")
    assert "error" in res
    assert "inconnue" in res["error"]


def test_read_session_stage_invalide(fake_output_root: Path) -> None:
    (fake_output_root / "x").mkdir()
    res = sess.read_session("x", stage="42")
    assert "error" in res


def test_read_session_etage_pas_lance(fake_output_root: Path) -> None:
    (fake_output_root / "x").mkdir()
    res = sess.read_session("x", stage="3")
    assert res["exists"] is False
    assert "pas encore" in res["message"]


def test_read_session_complete(fake_output_root: Path) -> None:
    d = fake_output_root / "abc"
    d.mkdir()
    rows = [{"nom": f"E{i}", "siren": f"100{i}"} for i in range(8)]
    _ecrire_csv(d / "etage3_contacts.csv", rows)
    res = sess.read_session("abc", stage="3", sample_size=3)
    assert res["exists"] is True
    assert res["row_count"] == 8
    assert len(res["sample"]) == 3
    assert res["sample"][0]["nom"] == "E0"


def test_read_session_rejette_path_traversal(fake_output_root: Path) -> None:
    """[S4e] un session_id qui s'évade de OUTPUT_ROOT est refusé, pas suivi."""
    res = sess.read_session("../../etc", stage="3")
    assert "error" in res
    assert "invalide" in res["error"]


def test_dossier_session_bloque_evasion(fake_output_root: Path) -> None:
    """[S4e] _dossier_session : ValueError hors racine, OK sinon."""
    with pytest.raises(ValueError):
        sess._dossier_session("../secret")
    ok = sess._dossier_session("bonne-session")
    assert ok.name == "bonne-session"
    assert ok.is_relative_to(fake_output_root.resolve())
