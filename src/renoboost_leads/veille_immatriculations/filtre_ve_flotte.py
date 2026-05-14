"""Filtrage VE flotte entreprise sur lignes AAA Data.

Garde les lignes qui sont à la fois :
- véhicule électrifié (énergie ∈ ENERGIES_ELECTRIQUES configurées)
- personne morale (type_acquereur ∈ TYPES_ACQUEREUR_MORALE configurés)
- SIREN renseigné si `exiger_siren=True`
"""

from __future__ import annotations

from ..common.logger import get_logger
from .models import LigneAAA, VeilleConfig

logger = get_logger(__name__)


def est_ve_flotte_entreprise(ligne: LigneAAA, config: VeilleConfig) -> tuple[bool, str | None]:
    """Renvoie (passe, raison_rejet).

    Si la ligne passe : (True, None).
    Sinon : (False, "raison textuelle courte").
    """
    if ligne.energie not in config.energies_conservees:
        return False, f"energie={ligne.energie} non électrifiée"

    if ligne.type_acquereur not in config.types_acquereur_morale:
        return False, f"acquereur={ligne.type_acquereur} pas personne morale"

    if config.exiger_siren and not ligne.siren:
        return False, "SIREN absent"

    return True, None


def filtrer_lignes_aaa(
    lignes: list[LigneAAA], config: VeilleConfig | None = None
) -> tuple[list[LigneAAA], dict[str, int]]:
    """Filtre une liste de LigneAAA.

    Returns:
        (lignes_retenues, compteurs_rejets) où compteurs_rejets associe la
        raison de rejet (string courte) au nombre de lignes concernées.
    """
    config = config or VeilleConfig()
    retenues: list[LigneAAA] = []
    rejets: dict[str, int] = {}

    for ligne in lignes:
        passe, raison = est_ve_flotte_entreprise(ligne, config)
        if passe:
            retenues.append(ligne)
        else:
            cle = (raison or "inconnu").split("=")[0]  # "energie", "acquereur", "SIREN absent"
            rejets[cle] = rejets.get(cle, 0) + 1

    logger.info(
        "Veille AAA filtrage : %d retenues / %d brutes — rejets : %s",
        len(retenues),
        len(lignes),
        rejets,
    )
    return retenues, rejets
