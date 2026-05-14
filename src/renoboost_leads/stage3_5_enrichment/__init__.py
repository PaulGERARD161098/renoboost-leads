"""Étage 3.5 — Enrichissement contacts vérifiés via Dropcontact (optionnel).

Inséré entre L3 (scraping/patterns) et L4 (scoring Claude). Récupère :
- email vérifié dirigeant (qualification SMTP)
- téléphone direct
- LinkedIn dirigeant + entreprise
- civilité / prénom / nom normalisés

Filtre intelligent : ne traite que les leads passant les filtres entreprise
(`hors_filtre_entreprise=False`) pour ne pas brûler de crédits sur des leads
qui ne seront pas démarchés.
"""

from .cache import CacheStage35
from .client import DropcontactClient, DropcontactClientConfig, DropcontactReponse
from .dry_run import DropcontactClientDryRun
from .enricher import EnricheurStage35

__all__ = [
    "CacheStage35",
    "DropcontactClient",
    "DropcontactClientConfig",
    "DropcontactReponse",
    "DropcontactClientDryRun",
    "EnricheurStage35",
]
