"""Tests du prompt caching dans le runner agent."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from renoboost_leads.agent import runner
from renoboost_leads.agent.budget import BudgetGuard
from renoboost_leads.agent.config import AgentConfig
from renoboost_leads.agent.journal import Journal


def _fake_response(
    *,
    text: str = "ok",
    stop_reason: str = "end_turn",
    in_tok: int = 100,
    out_tok: int = 20,
    cache_creation: int = 0,
    cache_read: int = 0,
):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        usage=SimpleNamespace(
            input_tokens=in_tok,
            output_tokens=out_tok,
            cache_creation_input_tokens=cache_creation,
            cache_read_input_tokens=cache_read,
        ),
    )


@pytest.fixture
def fixtures(tmp_path: Path) -> dict:
    cfg = AgentConfig(
        budget_eur_par_jour=1.0,
        max_outils_par_cycle=3,
        journal_path=str(tmp_path / "j.md"),
        budget_path=str(tmp_path / "b.json"),
    )
    return {
        "cfg": cfg,
        "journal": Journal(path=tmp_path / "j.md"),
        "budget": BudgetGuard(cap_eur_par_jour=1.0, path=tmp_path / "b.json"),
    }


def test_system_blocks_structure(tmp_path: Path) -> None:
    j = Journal(path=tmp_path / "j.md")
    blocks = runner._system_blocks(j)
    assert len(blocks) == 2
    assert blocks[0]["type"] == "text"
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
    # Le bloc journal n'est PAS caché (varie d'un cycle à l'autre)
    assert "cache_control" not in blocks[1]
    assert "Journal récent" in blocks[1]["text"]


def test_tools_cache_sur_dernier() -> None:
    schemas = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
    out = runner._tools_with_cache(schemas)
    assert len(out) == 3
    assert "cache_control" not in out[0]
    assert "cache_control" not in out[1]
    assert out[2]["cache_control"] == {"type": "ephemeral"}
    # L'original n'est pas muté
    assert "cache_control" not in schemas[2]


def test_tools_cache_liste_vide() -> None:
    assert runner._tools_with_cache([]) == []


def test_runner_passe_system_blocs(fixtures: dict) -> None:
    client = MagicMock()
    client.messages.create.return_value = _fake_response()
    runner.run_cycle(
        "x",
        config=fixtures["cfg"],
        journal=fixtures["journal"],
        budget=fixtures["budget"],
        client=client,
    )
    call = client.messages.create.call_args.kwargs
    assert isinstance(call["system"], list)
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    # Outils : au moins le dernier a cache_control
    assert any("cache_control" in t for t in call["tools"])


def test_runner_compte_cache_tokens(fixtures: dict) -> None:
    client = MagicMock()
    client.messages.create.return_value = _fake_response(
        in_tok=50, out_tok=20, cache_creation=2000, cache_read=8000
    )
    res = runner.run_cycle(
        "x",
        config=fixtures["cfg"],
        journal=fixtures["journal"],
        budget=fixtures["budget"],
        client=client,
    )
    assert res.tokens_cache_creation == 2000
    assert res.tokens_cache_read == 8000
    # Tarifs cache Sonnet 4.6 :
    # input 50/1M * 3 = 0.000150
    # output 20/1M * 15 = 0.000300
    # cache_write 2000/1M * 3 * 1.25 = 0.007500
    # cache_read  8000/1M * 3 * 0.10 = 0.002400
    # total USD = 0.010350 → * 0.92 = 0.009522 €
    assert res.cout_eur == pytest.approx(0.009522, abs=1e-5)


def test_runner_sans_cache_compatible(fixtures: dict) -> None:
    """Si l'API ne renvoie pas les champs cache_*, le runner ne plante pas."""
    client = MagicMock()
    # Pas d'attributs cache_creation_input_tokens / cache_read_input_tokens
    usage = SimpleNamespace(input_tokens=100, output_tokens=20)
    response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="ok")],
        stop_reason="end_turn",
        usage=usage,
    )
    client.messages.create.return_value = response
    res = runner.run_cycle(
        "x",
        config=fixtures["cfg"],
        journal=fixtures["journal"],
        budget=fixtures["budget"],
        client=client,
    )
    assert res.tokens_cache_creation == 0
    assert res.tokens_cache_read == 0
