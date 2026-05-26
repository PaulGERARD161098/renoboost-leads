"""Objet `Campagne` : exécution d'une verticale sur un territoire (zone/volume/budget)."""

from __future__ import annotations

from .composer import composer_campaign_config
from .launcher import persister_config_lancable
from .loader import CAMPAGNES_DIR, list_campagnes, load_campagne, save_campagne
from .schema import Campagne, IdentiteCampagne

__all__ = [
    "CAMPAGNES_DIR",
    "Campagne",
    "IdentiteCampagne",
    "composer_campaign_config",
    "list_campagnes",
    "load_campagne",
    "persister_config_lancable",
    "save_campagne",
]
