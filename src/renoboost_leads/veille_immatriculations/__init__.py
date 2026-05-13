"""Veille immatriculations VE — module ingestion AAA Data → pipeline RénoBoost.

Le client RénoBoost reçoit quotidiennement un fichier AAA Data des immatriculations
de véhicules électriques. Ce module :

1. Parse le CSV AAA (`parser_aaa.py`)
2. Filtre VE entreprise (`filtre_ve_flotte.py`)
3. Flag les SIREN déjà vus en VE (`etat_historique.py`)
4. Convertit en LeadStage2 (`adaptateur_lead_l2.py`)
5. Branche le pipeline existant L2 enrich → L3 → L4 (`pipeline_veille.py`)
6. Envoie le résumé du matin par email (`mailer.py`)
"""

from .filtre_ve_flotte import est_ve_flotte_entreprise, filtrer_lignes_aaa
from .models import (
    ENERGIES_ELECTRIQUES,
    TYPES_ACQUEREUR_MORALE,
    LigneAAA,
    VeilleConfig,
)
from .parser_aaa import ParseErrorAAA, lire_csv_aaa

__all__ = [
    "LigneAAA",
    "VeilleConfig",
    "ENERGIES_ELECTRIQUES",
    "TYPES_ACQUEREUR_MORALE",
    "lire_csv_aaa",
    "ParseErrorAAA",
    "est_ve_flotte_entreprise",
    "filtrer_lignes_aaa",
]
