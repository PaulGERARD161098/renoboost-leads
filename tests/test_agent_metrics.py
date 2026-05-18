"""Tests métriques agent (compteur par outil persisté)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from renoboost_leads.agent import runner
from renoboost_leads.agent.budget import BudgetGuard
from renoboost_leads.agent.config import AgentConfig
from renoboost_leads.agent.journal import Journal
from renoboost_leads.agent.metrics import MetricsStore


def test_load_si_pas_de_fichier(tmp_path: Path) -> None:
    m = MetricsStore(path=tmp_path / "m.json").load()
    assert m.cycles_total == 0
    assert m.par_outil == {}


def test_record_cycle_cumule(tmp_path: Path) -> None:
    s = MetricsStore(path=tmp_path / "m.json")
    m1 = s.record_cycle(
        cout_eur=0.01,
        outils=[
            {"name": "list_sessions", "duration_s": 0.1, "erreur": False},
            {"name": "read_session", "duration_s": 0.5, "erreur": False},
        ],
    )
    assert m1.cycles_total == 1
    assert m1.outils_total == 2
    assert m1.par_outil["list_sessions"].count == 1
    assert m1.par_outil["list_sessions"].duration_total_s == pytest.approx(0.1)

    m2 = s.record_cycle(
        cout_eur=0.02,
        outils=[{"name": "list_sessions", "duration_s": 0.2, "erreur": True}],
    )
    assert m2.cycles_total == 2
    assert m2.cout_total_eur == pytest.approx(0.03)
    assert m2.par_outil["list_sessions"].count == 2
    assert m2.par_outil["list_sessions"].duration_total_s == pytest.approx(0.3)
    assert m2.par_outil["list_sessions"].erreurs == 1


def test_persistance_entre_instances(tmp_path: Path) -> None:
    p = tmp_path / "m.json"
    MetricsStore(path=p).record_cycle(
        cout_eur=0.05,
        outils=[{"name": "x", "duration_s": 1.0, "erreur": False}],
    )
    m = MetricsStore(path=p).load()
    assert m.cycles_total == 1
    assert m.par_outil["x"].count == 1


def test_fichier_corrompu_reset(tmp_path: Path) -> None:
    p = tmp_path / "m.json"
    p.write_text("{pas du json", encoding="utf-8")
    m = MetricsStore(path=p).load()
    assert m.cycles_total == 0


def test_runner_persiste_metriques(tmp_path: Path) -> None:
    cfg = AgentConfig(
        budget_eur_par_jour=1.0,
        max_outils_par_cycle=3,
        journal_path=str(tmp_path / "j.md"),
        budget_path=str(tmp_path / "b.json"),
    )
    store = MetricsStore(path=tmp_path / "m.json")
    client = MagicMock()
    # Tour 1 : tool_use list_sessions ; tour 2 : end_turn
    client.messages.create.side_effect = [
        SimpleNamespace(
            content=[
                SimpleNamespace(
                    type="tool_use", name="list_sessions", input={}, id="tu1"
                )
            ],
            stop_reason="tool_use",
            usage=SimpleNamespace(input_tokens=100, output_tokens=20),
        ),
        SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=100, output_tokens=20),
        ),
    ]
    runner.run_cycle(
        "x",
        config=cfg,
        journal=Journal(path=tmp_path / "j.md"),
        budget=BudgetGuard(cap_eur_par_jour=1.0, path=tmp_path / "b.json"),
        client=client,
        metrics_store=store,
    )
    m = store.load()
    assert m.cycles_total == 1
    assert m.par_outil["list_sessions"].count == 1
    assert m.cout_total_eur > 0
