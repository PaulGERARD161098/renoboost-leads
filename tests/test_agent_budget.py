"""Tests du garde-fou budget €/jour."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from renoboost_leads.agent.budget import BudgetDepasseError, BudgetGuard


def test_budget_init_vierge(tmp_path: Path) -> None:
    g = BudgetGuard(cap_eur_par_jour=1.0, path=tmp_path / "b.json")
    assert g.cumul_eur == 0.0
    assert g.reste_eur == 1.0


def test_budget_consommer_accumule(tmp_path: Path) -> None:
    g = BudgetGuard(cap_eur_par_jour=1.0, path=tmp_path / "b.json")
    g.consommer(0.30)
    g.consommer(0.25)
    assert g.cumul_eur == pytest.approx(0.55)


def test_budget_persistance_entre_instances(tmp_path: Path) -> None:
    p = tmp_path / "b.json"
    g1 = BudgetGuard(cap_eur_par_jour=2.0, path=p)
    g1.consommer(0.40)
    g2 = BudgetGuard(cap_eur_par_jour=2.0, path=p)
    assert g2.cumul_eur == pytest.approx(0.40)


def test_budget_verifier_leve_si_atteint(tmp_path: Path) -> None:
    g = BudgetGuard(cap_eur_par_jour=0.10, path=tmp_path / "b.json")
    g.consommer(0.10)
    with pytest.raises(BudgetDepasseError):
        g.verifier()


def test_budget_verifier_ok_si_sous_cap(tmp_path: Path) -> None:
    g = BudgetGuard(cap_eur_par_jour=1.0, path=tmp_path / "b.json")
    g.consommer(0.50)
    g.verifier()  # ne lève pas


def test_budget_estimation_cout_sonnet() -> None:
    # 100 000 input + 10 000 output Sonnet : 100k*3$/M + 10k*15$/M = 0.30+0.15=0.45$
    # 0.45 * 0.92 = 0.414 €
    cout = BudgetGuard.estimer_cout_eur("claude-sonnet-4-6", 100_000, 10_000)
    assert cout == pytest.approx(0.414, abs=0.001)


def test_budget_estimation_cout_haiku() -> None:
    cout = BudgetGuard.estimer_cout_eur("claude-haiku-4-5", 100_000, 10_000)
    # 0.10 + 0.05 = 0.15 $ * 0.92 = 0.138 €
    assert cout == pytest.approx(0.138, abs=0.001)


def test_budget_estimation_modele_inconnu_renvoie_zero() -> None:
    assert BudgetGuard.estimer_cout_eur("modele-inconnu", 1000, 100) == 0.0


def test_budget_jour_change_reset(tmp_path: Path) -> None:
    p = tmp_path / "b.json"
    p.write_text(json.dumps({"jour": "2020-01-01", "cumul_eur": 99.0}), encoding="utf-8")
    g = BudgetGuard(cap_eur_par_jour=1.0, path=p)
    assert g.cumul_eur == 0.0


def test_budget_fichier_corrompu_reset(tmp_path: Path) -> None:
    p = tmp_path / "b.json"
    p.write_text("{ pas du json", encoding="utf-8")
    g = BudgetGuard(cap_eur_par_jour=1.0, path=p)
    assert g.cumul_eur == 0.0


def test_budget_cap_invalide() -> None:
    with pytest.raises(ValueError):
        BudgetGuard(cap_eur_par_jour=0.0)


def test_budget_consommer_negatif_erreur(tmp_path: Path) -> None:
    g = BudgetGuard(cap_eur_par_jour=1.0, path=tmp_path / "b.json")
    with pytest.raises(ValueError):
        g.consommer(-0.1)
