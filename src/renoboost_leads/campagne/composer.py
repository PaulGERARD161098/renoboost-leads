"""Composition `Campagne` + `Verticale` → `CampaignConfig`.

C'est le pont vers l'existant : le pipeline L1→L4 consomme un `CampaignConfig`
(`config/<client>.yaml`). On le fabrique ici à partir de l'offre (verticale) et
de l'exécution (campagne), sans rien modifier au pipeline. Le lancement
proprement dit reste l'affaire d'un étage ultérieur (D4).

Mapping :
- secteurs, filtres entreprise, seuil de scoring, activation L3.5  ← verticale
- zone, volume, budget                                            ← campagne
- contexte de scoring Claude (offre + cible)                      ← verticale
"""

from __future__ import annotations

from datetime import date

from ..models import (
    CampaignConfig,
    ClaudeScoring,
    EnrichissementL35,
    Filtres,
    RunInfo,
    Sortie,
    StagesFlags,
)
from ..verticale.schema import Verticale
from .schema import Campagne


def _contexte_client(verticale: Verticale) -> str:
    return (
        f"{verticale.offre.produit}. {verticale.offre.argument_principal} "
        f"Cible : {verticale.cible.detail}"
    )


def composer_campaign_config(campagne: Campagne, verticale: Verticale) -> CampaignConfig:
    """Compose un `CampaignConfig` lançable depuis une campagne + sa verticale.

    Lève `ValueError` si la verticale ne correspond pas au slug référencé par
    la campagne.
    """
    if verticale.slug != campagne.verticale_slug:
        raise ValueError(
            f"verticale '{verticale.slug}' ≠ campagne.verticale_slug="
            f"'{campagne.verticale_slug}'."
        )

    l3_5_actif = verticale.enrichissements.l3_5_dropcontact

    return CampaignConfig(
        run=RunInfo(
            client_name=campagne.id,
            description=(
                f"Campagne « {campagne.campagne.nom or campagne.id} » — "
                f"verticale {verticale.slug}"
            ),
            campaign_date=campagne.campagne.created or date.today().isoformat(),
        ),
        stages=StagesFlags(
            enable_stage_1_decouverte=True,
            enable_stage_2_entreprises=True,
            enable_stage_3_contacts=True,
            enable_stage_3_5_enrichment=l3_5_actif,
            enable_stage_4_prospection=True,
        ),
        secteurs=verticale.cibles.secteurs_places,
        zone=campagne.zone,
        filtres=Filtres(),
        filtres_entreprise=verticale.cibles.filtres_entreprise,
        enrichissement_l3_5=EnrichissementL35(),
        claude_scoring=ClaudeScoring(
            seuil_top_lead=verticale.qualification.seuil_score_top,
            contexte_client=_contexte_client(verticale),
        ),
        volume=campagne.volume,
        budget=campagne.budget,
        sortie=Sortie(),
    )
