"""Garde-fou budget €/jour pour l'agent.

Persistance : `data/agent/budget.json` — état du jour (date, cumul €).
Au passage minuit (UTC), le compteur repart à 0. Si le cap est atteint,
l'agent reçoit une erreur claire et journalise.

Tarifs Claude indicatifs (à ajuster si Anthropic change) :
- Sonnet 4.6 : 3 $/Mtok input, 15 $/Mtok output
- Haiku 4.5  : 1 $/Mtok input, 5 $/Mtok output

On approxime 1 $ = 0.92 €. Les tarifs servent juste à *estimer* le coût des
appels — la vérité reste la facture Anthropic.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from ..settings import PROJECT_ROOT

BUDGET_DEFAULT_PATH = PROJECT_ROOT / "data" / "agent" / "budget.json"

TARIFS_USD_PER_MTOK = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-opus-4-7": {"input": 15.0, "output": 75.0},
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
}
USD_TO_EUR = 0.92


class BudgetDepasseError(RuntimeError):
    """Levée quand le cap journalier est atteint."""


@dataclass
class EtatBudget:
    jour: str  # YYYY-MM-DD UTC
    cumul_eur: float

    @classmethod
    def vierge(cls) -> EtatBudget:
        return cls(jour=date.today().isoformat(), cumul_eur=0.0)


class BudgetGuard:
    """Tracker persistant €/jour avec cap dur."""

    def __init__(self, cap_eur_par_jour: float, path: Path | None = None) -> None:
        if cap_eur_par_jour <= 0:
            raise ValueError("cap_eur_par_jour doit être > 0")
        self.cap = float(cap_eur_par_jour)
        self.path = path or BUDGET_DEFAULT_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._etat = self._charger_ou_init()

    def _charger_ou_init(self) -> EtatBudget:
        if not self.path.exists():
            return EtatBudget.vierge()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            etat = EtatBudget(**raw)
        except (json.JSONDecodeError, TypeError, KeyError):
            return EtatBudget.vierge()
        if etat.jour != date.today().isoformat():
            return EtatBudget.vierge()
        return etat

    def _sauver(self) -> None:
        self.path.write_text(json.dumps(asdict(self._etat), indent=2), encoding="utf-8")

    @staticmethod
    def estimer_cout_eur(
        modele: str, tokens_input: int, tokens_output: int
    ) -> float:
        tarifs = TARIFS_USD_PER_MTOK.get(modele)
        if tarifs is None:
            return 0.0
        cout_usd = (
            tokens_input / 1_000_000 * tarifs["input"]
            + tokens_output / 1_000_000 * tarifs["output"]
        )
        return round(cout_usd * USD_TO_EUR, 6)

    @property
    def cumul_eur(self) -> float:
        return self._etat.cumul_eur

    @property
    def reste_eur(self) -> float:
        return max(0.0, self.cap - self._etat.cumul_eur)

    def verifier(self) -> None:
        """Lève BudgetDepasseError si on a déjà atteint le cap."""
        if self._etat.cumul_eur >= self.cap:
            raise BudgetDepasseError(
                f"Cap journalier atteint : {self._etat.cumul_eur:.4f} € / {self.cap:.2f} €. "
                "Relance demain (UTC) ou augmente `agent.budget_eur_par_jour`."
            )

    def consommer(self, cout_eur: float) -> None:
        """Ajoute un coût au cumul. À appeler après chaque appel Claude réussi."""
        if cout_eur < 0:
            raise ValueError("cout_eur doit être >= 0")
        self._etat.cumul_eur = round(self._etat.cumul_eur + cout_eur, 6)
        self._sauver()
