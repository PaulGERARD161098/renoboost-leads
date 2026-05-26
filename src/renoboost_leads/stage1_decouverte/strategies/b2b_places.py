"""Stratégie de découverte L1 pour cible B2B : Google Places.

En V0, la découverte B2B est assurée par l'extracteur Google Places existant.
La V1 ajoutera d'autres stratégies (ex. `b2c_particulier`) dans ce dossier,
enregistrées dans `orchestrator.py`, sans modifier le cœur du pipeline.
"""

from __future__ import annotations

from ..extractor import ExtracteurStage1

StrategieDecouverteB2B = ExtracteurStage1
