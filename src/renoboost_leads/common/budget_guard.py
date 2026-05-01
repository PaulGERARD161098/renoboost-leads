"""Budget Guard — protection hardcodée contre dépassement de coût.

Comportement :
- À chaque appel API, on accumule le coût estimé
- Si le total dépasse le plafond, on lève BudgetExceededError
- Le caller doit attraper l'exception et arrêter proprement
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from .logger import get_logger

logger = get_logger(__name__)


class BudgetExceededError(Exception):
    """Levée quand le budget configuré est dépassé."""


@dataclass
class BudgetGuard:
    """Tracke le coût cumulé d'un run."""

    plafond_eur: float
    cout_actuel_eur: float = 0.0
    nb_appels: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def ajouter_cout(self, montant_eur: float, contexte: str = "") -> None:
        """Ajoute un coût au compteur. Lève BudgetExceededError si dépassement.

        Args:
            montant_eur: coût de l'opération en euros
            contexte: description (pour les logs)
        """
        with self._lock:
            nouveau_total = self.cout_actuel_eur + montant_eur

            if nouveau_total > self.plafond_eur:
                logger.error(
                    "Budget dépassé : %.4f € + %.4f € = %.4f € > plafond %.2f € (%s)",
                    self.cout_actuel_eur,
                    montant_eur,
                    nouveau_total,
                    self.plafond_eur,
                    contexte,
                    extra={
                        "event": "budget_exceeded",
                        "cout_actuel": self.cout_actuel_eur,
                        "montant_demande": montant_eur,
                        "plafond": self.plafond_eur,
                        "contexte": contexte,
                    },
                )
                raise BudgetExceededError(
                    f"Plafond de {self.plafond_eur:.2f} € atteint "
                    f"(actuel : {self.cout_actuel_eur:.4f} € + {montant_eur:.4f} € demandé)"
                )

            self.cout_actuel_eur = nouveau_total
            self.nb_appels += 1

            # Alerte à 80% du plafond
            ratio = self.cout_actuel_eur / self.plafond_eur
            if ratio >= 0.8 and (self.nb_appels % 10 == 0 or ratio >= 0.95):
                logger.warning(
                    "Budget consommé à %.0f%% (%.4f / %.2f €)",
                    ratio * 100,
                    self.cout_actuel_eur,
                    self.plafond_eur,
                )

    def restant_eur(self) -> float:
        return max(0.0, self.plafond_eur - self.cout_actuel_eur)

    def peut_continuer(self, cout_estime_eur: float = 0.0) -> bool:
        return (self.cout_actuel_eur + cout_estime_eur) <= self.plafond_eur

    def resume(self) -> dict[str, float | int]:
        return {
            "plafond_eur": self.plafond_eur,
            "cout_actuel_eur": round(self.cout_actuel_eur, 4),
            "restant_eur": round(self.restant_eur(), 4),
            "nb_appels": self.nb_appels,
            "ratio_consomme": round(self.cout_actuel_eur / self.plafond_eur, 3),
        }
