"""Tests du loader de config agent."""

from __future__ import annotations

from pathlib import Path

import pytest

from renoboost_leads.agent.config import AgentConfig, load_agent_config


def test_load_defaults_si_pas_de_fichier(tmp_path: Path) -> None:
    cfg = load_agent_config(tmp_path / "inexistant.yaml")
    assert cfg.modele_principal == "claude-sonnet-4-6"
    assert cfg.budget_eur_par_jour == 5.0


def test_load_yaml_complet(tmp_path: Path) -> None:
    p = tmp_path / "agent.yaml"
    p.write_text(
        """
modele_principal: claude-opus-4-7
budget_eur_par_jour: 12.0
niveau_autonomie: N3
alerte_destinataires:
  - a@b.fr
  - c@d.fr
""",
        encoding="utf-8",
    )
    cfg = load_agent_config(p)
    assert cfg.modele_principal == "claude-opus-4-7"
    assert cfg.budget_eur_par_jour == 12.0
    assert cfg.niveau_autonomie == "N3"
    assert cfg.alerte_destinataires == ["a@b.fr", "c@d.fr"]


def test_load_ignore_champ_inconnu(tmp_path: Path) -> None:
    p = tmp_path / "agent.yaml"
    p.write_text("modele_principal: x\nclef_inconnue: 42\n", encoding="utf-8")
    cfg = load_agent_config(p)
    assert cfg.modele_principal == "x"


def test_load_yaml_invalide(tmp_path: Path) -> None:
    p = tmp_path / "agent.yaml"
    p.write_text("- liste\n- au\n- lieu\n- de mapping\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_agent_config(p)


def test_chemin_absolu_journal() -> None:
    cfg = AgentConfig(journal_path="data/agent/x.md")
    p = cfg.journal_path_abs()
    assert p.is_absolute()
    assert p.name == "x.md"
