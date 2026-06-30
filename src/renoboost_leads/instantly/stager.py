"""Création d'un staging cold-mail à partir d'une session du pipeline principal.

Pendant que `parkings_aper/staging_instantly.py` stage les leads APER, ce module
stage les leads du pipeline principal (L4, `etage4_prospection.csv`). Rien n'est
envoyé : on alimente la file de validation humaine N2 (`cold-mail show/validate/
send`). Chaque lead retenu devient un `StagedItem` (objet + corps issus de L4).

Sélection : `top_lead` par défaut ; `min_score` élargit aux leads
`score_interet >= min_score`. Un lead hors filtre entreprise n'est JAMAIS retenu
(on ne cold-mail pas une cible hors ICP). Les leads sans email exploitable sont
écartés et comptés.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..exporter import lire_stage4_csv
from ..models import LeadStage4
from ..settings import PROJECT_ROOT
from .staging import StagedItem, Staging, StagingStore, nouveau_staging_id


@dataclass
class ResultatStaging:
    staging_id: str
    nb_stages: int = 0
    nb_sans_email: int = 0
    nb_sous_seuil: int = 0


def _email_dest(lead: LeadStage4) -> str | None:
    """Meilleure adresse exploitable : Dropcontact vérifié > email scrapé."""
    if lead.email_dropcontact:
        return lead.email_dropcontact
    if lead.emails_verifies:
        return lead.emails_verifies[0]
    return None


def _nom_dest(lead: LeadStage4) -> str:
    nom = " ".join(p for p in (lead.dirigeant_prenom, lead.dirigeant_nom) if p).strip()
    return nom or lead.nom


def _retenu(lead: LeadStage4, min_score: int | None) -> bool:
    if lead.hors_filtre_entreprise:
        return False
    if lead.top_lead:
        return True
    return min_score is not None and (lead.score_interet or 0) >= min_score


def stager_leads_l4(
    leads: list[LeadStage4],
    *,
    secteur: str,
    session_id: str,
    from_email: str,
    min_score: int | None = None,
    store: StagingStore | None = None,
) -> ResultatStaging:
    """Crée et persiste un staging cold-mail à partir de leads L4 scorés."""
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
                lead_id=lead.siren or lead.place_id,
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


def stager_session(
    session_id: str,
    *,
    from_email: str,
    secteur: str = "pipeline",
    min_score: int | None = None,
    store: StagingStore | None = None,
    output_base: Path | None = None,
) -> ResultatStaging:
    """Charge `etage4_prospection.csv` d'une session et crée le staging."""
    base = output_base or (PROJECT_ROOT / "data" / "output")
    csv_path = base / session_id / "etage4_prospection.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"CSV L4 introuvable pour la session '{session_id}' : {csv_path}. "
            "Lance d'abord --stages 4 sur cette session."
        )
    leads = lire_stage4_csv(csv_path)
    return stager_leads_l4(
        leads,
        secteur=secteur,
        session_id=session_id,
        from_email=from_email,
        min_score=min_score,
        store=store,
    )
