"""Stratégie de contacts L3 pour cible B2B : scraping + patterns.

En V0, la récupération de contacts B2B est assurée par l'enricheur L3 existant.
La V1 ajoutera d'autres stratégies (ex. sources particuliers) ici.
"""

from __future__ import annotations

from ..enricher import EnricheurStage3

StrategieContactsB2B = EnricheurStage3
