"""Conversion LigneAAA → LeadStage1 prêt pour le pipeline RénoBoost.

On a déjà SIREN + raison_sociale + dept côté AAA, donc on injecte ces infos
dans un LeadStage1 et on laisse les enrichers L2/L3/L4 existants faire leur
travail. Le SIREN AAA sera confronté à celui retourné par data.gouv.fr —
en cas de divergence, c'est data.gouv qui fait foi (donnée officielle).
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..models import LeadStage1
from .models import LigneAAA


def _place_id_factice(ligne: LigneAAA) -> str:
    """Génère un place_id factice unique stable pour cette ligne AAA."""
    siren = ligne.siren or "NOSIREN"
    return f"AAA_{ligne.date_immatriculation.isoformat()}_{siren}"


def _marque_modele(ligne: LigneAAA) -> str:
    parts = [p for p in (ligne.marque, ligne.modele) if p]
    return " ".join(parts) if parts else ""


def lignaaa_vers_lead_stage1(ligne: LigneAAA) -> LeadStage1:
    """Convertit une LigneAAA en LeadStage1 (point d'entrée pipeline standard)."""
    return LeadStage1(
        place_id=_place_id_factice(ligne),
        extraction_date=datetime.now(timezone.utc),
        nom=ligne.raison_sociale or _marque_modele(ligne) or f"SIREN {ligne.siren or '?'}",
        adresse=None,
        ville=ligne.commune,
        code_postal=ligne.code_postal,
        secteur_recherche=f"veille_ve_{ligne.energie.lower()}",
        requete_origine=f"AAA_Data {ligne.date_immatriculation.isoformat()}",
    )
