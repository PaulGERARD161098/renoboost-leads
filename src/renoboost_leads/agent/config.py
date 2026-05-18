"""Chargement de `config/agent.yaml`."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..settings import PROJECT_ROOT

AGENT_CONFIG_DEFAULT_PATH = PROJECT_ROOT / "config" / "agent.yaml"


@dataclass
class AgentConfig:
    modele_principal: str = "claude-sonnet-4-6"
    modele_boucle: str = "claude-haiku-4-5"
    budget_eur_par_jour: float = 5.0
    max_outils_par_cycle: int = 12
    niveau_autonomie: str = "N2"
    journal_path: str = "data/agent/journal.md"
    budget_path: str = "data/agent/budget.json"
    alerte_destinataires: list[str] = field(default_factory=list)

    def journal_path_abs(self) -> Path:
        return _abs(self.journal_path)

    def budget_path_abs(self) -> Path:
        return _abs(self.budget_path)


def _abs(p: str) -> Path:
    path = Path(p)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def load_agent_config(path: Path | None = None) -> AgentConfig:
    path = path or AGENT_CONFIG_DEFAULT_PATH
    if not path.exists():
        return AgentConfig()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path} doit contenir un mapping YAML.")
    # Filtre aux champs connus pour éviter TypeError sur clés étrangères.
    champs_valides = set(AgentConfig.__dataclass_fields__.keys())
    filtre = {k: v for k, v in raw.items() if k in champs_valides}
    return AgentConfig(**filtre)
