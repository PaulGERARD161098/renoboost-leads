"""Objet `Verticale` : l'unité pivotable de la plateforme de prospection."""

from __future__ import annotations

from .loader import VERTICALES_DIR, VerticaleHorsV0Error, list_verticales, load_verticale
from .schema import Verticale

__all__ = [
    "VERTICALES_DIR",
    "Verticale",
    "VerticaleHorsV0Error",
    "list_verticales",
    "load_verticale",
]
