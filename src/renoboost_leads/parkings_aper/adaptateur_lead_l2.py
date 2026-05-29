"""Conversion LigneParking → LeadStage1 prêt pour le pipeline RénoBoost.

On injecte ce que l'on connaît du parking (enseigne/exploitant, CP, commune,
SIREN éventuel) dans un LeadStage1, et on laisse les enrichers L2/L3/L4 retrouver
l'entreprise. Le contexte « ombrière obligatoire loi APER » est embarqué dans
`requete_origine` pour rester traçable jusqu'au scoring.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..models import LeadStage1
from .models import LigneParking


def _place_id_factice(ligne: LigneParking) -> str:
    return f"APER_{ligne.identifiant_stable()}"


def ligne_parking_vers_lead_stage1(ligne: LigneParking) -> LeadStage1:
    """Convertit une LigneParking en LeadStage1 (point d'entrée pipeline standard)."""
    echeance, priorite = ligne.echeance()
    nom = (
        ligne.raison_sociale
        or ligne.nom
        or (f"SIREN {ligne.siren}" if ligne.siren else None)
        or f"Parking {int(ligne.surface_m2)} m² {ligne.commune or ''}".strip()
    )
    return LeadStage1(
        place_id=_place_id_factice(ligne),
        extraction_date=datetime.now(timezone.utc),
        nom=nom,
        adresse=ligne.adresse,
        ville=ligne.commune,
        code_postal=ligne.code_postal,
        latitude=ligne.latitude,
        longitude=ligne.longitude,
        secteur_recherche="aper_ombriere_parking",
        requete_origine=(
            f"Parking {int(ligne.surface_m2)} m² soumis loi APER "
            f"(échéance {echeance}, priorité {priorite})"
        ),
    )
