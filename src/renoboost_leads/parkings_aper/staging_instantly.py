"""Porte b — pousse les top leads APER dans le staging cold-mail Instantly.

Rien n'est envoyé directement : on alimente la file de **validation humaine N2**
(`instantly.staging`). Chaque top lead APER devient un `StagedItem` (email +
objet + corps issus du scoring L4), que l'utilisateur valide/refuse ensuite via
`cold-mail show/validate/send`.

Sélection : par défaut les `top_lead` uniquement ; `min_score` élargit aux leads
dont `score_interet >= min_score`. Les leads écartés par les filtres entreprise
(`hors_filtre_entreprise`) ne sont JAMAIS retenus, même via `min_score` : on ne
cold-mail pas une cible explicitement hors ICP. Les leads sans email exploitable
sont écartés (on ne peut pas cold-mailer sans adresse) et comptés.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..instantly.staging import (
    StagedItem,
    Staging,
    StagingStore,
    nouveau_staging_id,
)
from ..models import LeadAper


@dataclass
class ResultatStaging:
    staging_id: str
    nb_stages: int = 0
    nb_sans_email: int = 0
    nb_sous_seuil: int = 0


def _email_dest(lead: LeadAper) -> str | None:
    """Meilleure adresse exploitable : Dropcontact vérifié > email scrapé."""
    if getattr(lead, "email_dropcontact", None):
        return lead.email_dropcontact
    if lead.emails_verifies:
        return lead.emails_verifies[0]
    return None


def _nom_dest(lead: LeadAper) -> str:
    nom = " ".join(p for p in (lead.dirigeant_prenom, lead.dirigeant_nom) if p).strip()
    return nom or lead.nom


def _retenu(lead: LeadAper, min_score: int | None) -> bool:
    # Un lead hors filtre entreprise ne part jamais en cold-mail, quel que soit
    # son score (la voie `min_score` court-circuitait `top_lead`).
    if getattr(lead, "hors_filtre_entreprise", False):
        return False
    if lead.top_lead:
        return True
    if min_score is not None and (lead.score_interet or 0) >= min_score:
        return True
    return False


def stager_leads_aper(
    leads: list[LeadAper],
    *,
    secteur: str,
    session_id: str,
    from_email: str,
    min_score: int | None = None,
    store: StagingStore | None = None,
) -> ResultatStaging:
    """Crée et persiste un staging cold-mail à partir de leads APER scorés."""
    store = store or StagingStore()
    items: list[StagedItem] = []
    nb_sans_email = 0
    nb_sous_seuil = 0

    for lead in leads:
        if not _retenu(lead, min_score):
            nb_sous_seuil += 1
            continue
        email = _email_dest(lead)
        if not email:
            nb_sans_email += 1
            continue
        sujet = lead.email_objet or f"Ombrières photovoltaïques — {lead.nom}"
        corps = lead.email_corps or lead.pitch_propose or ""
        items.append(
            StagedItem(
                lead_id=lead.siren or lead.identifiant_parking or lead.place_id,
                email_dest=email,
                nom_dest=_nom_dest(lead),
                sujet=sujet,
                corps=corps,
            )
        )

    staging = Staging(
        staging_id=nouveau_staging_id(),
        secteur=secteur,
        session_id=session_id,
        from_email=from_email,
        items=items,
    )
    store.save(staging)
    return ResultatStaging(
        staging_id=staging.staging_id,
        nb_stages=len(items),
        nb_sans_email=nb_sans_email,
        nb_sous_seuil=nb_sous_seuil,
    )
