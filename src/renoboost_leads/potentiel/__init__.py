"""Analyse du potentiel d'un prospect pour Rossini Energy.

Trois potentiels indépendants, notés /10 :
- solaire (toiture),
- ombrières (parking),
- bornes de recharge VE.

Le scoring est une logique pure (`scoring.py`, testée hors réseau). Les sources de
données (orthophoto IGN + Claude Vision, emprise bâtie IGN, jeu IRVE data.gouv) sont
des connecteurs tolérants : toute panne renvoie None/[] sans bloquer le run.
"""

from __future__ import annotations

from .models import AnalysePotentiels, PotentielBornes, PotentielOmbrieres, PotentielSolaire

__all__ = [
    "AnalysePotentiels",
    "PotentielBornes",
    "PotentielOmbrieres",
    "PotentielSolaire",
]
