"""Stratégie d'enrichissement L2 pour cible B2B : SIREN/SIRET (data.gouv.fr).

En V0, l'enrichissement B2B est assuré par l'enricheur entreprises existant.
La V1 ajoutera d'autres stratégies (ex. enrichissement particulier) ici.
"""

from __future__ import annotations

from ..enricher import EnricheurStage2

StrategieEntreprisesB2B = EnricheurStage2
