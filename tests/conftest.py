"""Configuration globale pytest.

Isole les chemins par défaut de l'agent (journal, budget, métriques)
vers un dossier tmp_path pour chaque test, pour éviter que les tests
qui n'overrident pas explicitement le path ne polluent `data/agent/`.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isoler_chemins_agent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Redirige les paths agent par défaut vers tmp_path."""
    from renoboost_leads.agent import budget as agent_budget
    from renoboost_leads.agent import journal as agent_journal
    from renoboost_leads.agent import metrics as agent_metrics

    monkeypatch.setattr(
        agent_journal, "JOURNAL_DEFAULT_PATH", tmp_path / "journal.md"
    )
    monkeypatch.setattr(
        agent_budget, "BUDGET_DEFAULT_PATH", tmp_path / "budget.json"
    )
    monkeypatch.setattr(
        agent_metrics, "METRICS_DEFAULT_PATH", tmp_path / "metrics.json"
    )
