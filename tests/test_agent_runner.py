"""Tests du runner agent (Claude API mocké)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from renoboost_leads.agent import runner
from renoboost_leads.agent.budget import BudgetDepasseError, BudgetGuard
from renoboost_leads.agent.config import AgentConfig
from renoboost_leads.agent.journal import Journal


def _fake_response(
    *, text: str | None = None, tool_use: tuple[str, dict, str] | None = None,
    stop_reason: str = "end_turn", in_tok: int = 100, out_tok: int = 20,
):
    """Construit une fausse réponse SDK-like."""
    content = []
    if text:
        content.append(SimpleNamespace(type="text", text=text))
    if tool_use:
        name, inp, tuid = tool_use
        content.append(SimpleNamespace(type="tool_use", name=name, input=inp, id=tuid))
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok),
    )


@pytest.fixture
def _fixtures(tmp_path: Path) -> dict:
    cfg = AgentConfig(
        modele_principal="claude-sonnet-4-6",
        budget_eur_par_jour=1.0,
        max_outils_par_cycle=5,
        journal_path=str(tmp_path / "journal.md"),
        budget_path=str(tmp_path / "budget.json"),
    )
    return {
        "cfg": cfg,
        "journal": Journal(path=tmp_path / "journal.md"),
        "budget": BudgetGuard(cap_eur_par_jour=1.0, path=tmp_path / "budget.json"),
    }


def test_run_cycle_simple_texte(_fixtures: dict) -> None:
    fix = _fixtures
    client = MagicMock()
    client.messages.create.return_value = _fake_response(text="ok pilote analysé")
    res = runner.run_cycle(
        "diagnostique la dernière session",
        config=fix["cfg"],
        journal=fix["journal"],
        budget=fix["budget"],
        client=client,
    )
    assert res.tours == 1
    assert res.stop_reason == "end_turn"
    assert res.texte_final == "ok pilote analysé"
    assert res.outils_appeles == []
    assert res.cout_eur > 0


def test_run_cycle_avec_un_outil(_fixtures: dict) -> None:
    fix = _fixtures
    # Tour 1 : tool_use list_sessions
    # Tour 2 : réponse texte
    client = MagicMock()
    client.messages.create.side_effect = [
        _fake_response(
            tool_use=("list_sessions", {"limit": 5}, "tu_1"),
            stop_reason="tool_use",
        ),
        _fake_response(text="J'ai vu 0 session.", stop_reason="end_turn"),
    ]
    res = runner.run_cycle(
        "liste les sessions",
        config=fix["cfg"],
        journal=fix["journal"],
        budget=fix["budget"],
        client=client,
    )
    assert res.tours == 2
    assert len(res.outils_appeles) == 1
    assert res.outils_appeles[0]["name"] == "list_sessions"
    assert "0 session" in res.texte_final
    # Le journal a une entrée
    entries = fix["journal"].read_recent(10)
    assert len(entries) == 1
    assert "list_sessions" in entries[0]


def test_run_cycle_outil_inconnu(_fixtures: dict) -> None:
    fix = _fixtures
    client = MagicMock()
    client.messages.create.side_effect = [
        _fake_response(
            tool_use=("outil_imaginaire", {}, "tu_x"), stop_reason="tool_use"
        ),
        _fake_response(text="hmm, outil pas dispo", stop_reason="end_turn"),
    ]
    res = runner.run_cycle(
        "fais un truc",
        config=fix["cfg"],
        journal=fix["journal"],
        budget=fix["budget"],
        client=client,
    )
    # L'outil n'a quand même pas planté le cycle — le résultat 'error' est
    # passé au LLM qui répond ensuite normalement.
    assert res.tours == 2
    assert res.outils_appeles[0]["name"] == "outil_imaginaire"


def test_run_cycle_budget_depasse_avant(_fixtures: dict) -> None:
    fix = _fixtures
    fix["budget"].consommer(1.0)  # cap atteint
    client = MagicMock()
    with pytest.raises(BudgetDepasseError):
        runner.run_cycle(
            "x",
            config=fix["cfg"],
            journal=fix["journal"],
            budget=fix["budget"],
            client=client,
        )
    client.messages.create.assert_not_called()


def test_run_cycle_stop_max_outils(_fixtures: dict) -> None:
    fix = _fixtures
    fix["cfg"].max_outils_par_cycle = 2
    client = MagicMock()
    # Toujours tool_use → la boucle doit casser après max_outils+1 tours
    client.messages.create.return_value = _fake_response(
        tool_use=("list_sessions", {}, "tu_loop"), stop_reason="tool_use"
    )
    res = runner.run_cycle(
        "boucle",
        config=fix["cfg"],
        journal=fix["journal"],
        budget=fix["budget"],
        client=client,
    )
    # max_outils=2 → boucle range(3) → 3 tours max
    assert res.tours <= 3
    assert client.messages.create.call_count <= 3


def test_run_cycle_decompte_tokens(_fixtures: dict) -> None:
    fix = _fixtures
    client = MagicMock()
    client.messages.create.return_value = _fake_response(
        text="ok", in_tok=12345, out_tok=678
    )
    res = runner.run_cycle(
        "x",
        config=fix["cfg"],
        journal=fix["journal"],
        budget=fix["budget"],
        client=client,
    )
    assert res.tokens_input == 12345
    assert res.tokens_output == 678
    # Sonnet : (12345*3 + 678*15)/1M = 0.047205 $ * 0.92 = 0.04343 €
    assert res.cout_eur == pytest.approx(0.04342866, abs=1e-5)
