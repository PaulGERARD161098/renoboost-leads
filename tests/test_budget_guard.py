"""Tests unitaires du Budget Guard."""

from __future__ import annotations

import pytest

from renoboost_leads.common.budget_guard import BudgetExceededError, BudgetGuard


class TestBudgetGuard:
    def test_petite_addition_ok(self):
        b = BudgetGuard(plafond_eur=10.0)
        b.ajouter_cout(2.5, "test")
        assert b.cout_actuel_eur == 2.5
        assert b.nb_appels == 1

    def test_plusieurs_ajouts(self):
        b = BudgetGuard(plafond_eur=10.0)
        b.ajouter_cout(2.0, "a")
        b.ajouter_cout(3.0, "b")
        b.ajouter_cout(1.5, "c")
        assert b.cout_actuel_eur == 6.5
        assert b.nb_appels == 3

    def test_depassement_leve_exception(self):
        b = BudgetGuard(plafond_eur=5.0)
        b.ajouter_cout(3.0)
        with pytest.raises(BudgetExceededError, match="Plafond"):
            b.ajouter_cout(2.5)
        # L'ajout qui aurait dépassé est rejeté
        assert b.cout_actuel_eur == 3.0

    def test_egal_au_plafond_ok(self):
        b = BudgetGuard(plafond_eur=10.0)
        b.ajouter_cout(10.0)
        assert b.cout_actuel_eur == 10.0
        # L'ajout suivant doit échouer
        with pytest.raises(BudgetExceededError):
            b.ajouter_cout(0.01)

    def test_restant(self):
        b = BudgetGuard(plafond_eur=10.0)
        b.ajouter_cout(3.0)
        assert b.restant_eur() == 7.0

    def test_peut_continuer(self):
        b = BudgetGuard(plafond_eur=10.0)
        b.ajouter_cout(7.0)
        assert b.peut_continuer(2.0)
        assert b.peut_continuer(3.0)
        assert not b.peut_continuer(3.5)

    def test_resume(self):
        b = BudgetGuard(plafond_eur=10.0)
        b.ajouter_cout(2.0)
        b.ajouter_cout(3.0)
        r = b.resume()
        assert r["plafond_eur"] == 10.0
        assert r["cout_actuel_eur"] == 5.0
        assert r["restant_eur"] == 5.0
        assert r["nb_appels"] == 2
        assert r["ratio_consomme"] == 0.5
