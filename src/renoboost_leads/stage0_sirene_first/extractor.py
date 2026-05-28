"""Orchestrateur de l'étage 0 — Découverte SIRENE-first.

Itère sur recherche-entreprises.api.gouv.fr avec les filtres natifs (zone +
NAF + tranche d'effectif + CA + catégorie), mappe chaque entreprise en
LeadStage2, déduplique par SIREN, plafonne au volume cible.

Contrairement à l'étage 1 Places-first, on n'a pas de grille géographique
ni de tour par "secteur" : l'API fait le travail de filtrage et nous renvoie
directement les bons leads.
"""

from __future__ import annotations

from ..common.logger import get_logger
from ..models import CampaignConfig, LeadStage2
from ..stage2_entreprises.filters import _TRANCHES_INSEE
from ..stage2_entreprises.recherche_client import RechercheEntreprisesClient
from .mapper import entreprise_to_lead_stage2

logger = get_logger(__name__)


def tranches_pour_effectif(
    effectif_min: int | None,
    effectif_max: int | None,
) -> list[str]:
    """Renvoie les codes INSEE des tranches qui chevauchent [emin, emax].

    Permet de pré-filtrer l'appel API : on ne demande que les tranches qui
    pourraient contenir des entreprises de la cible. Le filtre fin reste
    appliqué post-réception via les filtres entreprise (l'INSEE encode des
    intervalles, donc une tranche [50-99] passera même si max=50).
    """
    if effectif_min is None and effectif_max is None:
        return []
    emin = effectif_min if effectif_min is not None else 0
    emax = effectif_max if effectif_max is not None else 999_999

    codes: list[str] = []
    for code, (tmin, tmax_raw) in _TRANCHES_INSEE.items():
        tmax = tmax_raw if tmax_raw is not None else 999_999
        if tmax < emin or tmin > emax:
            continue
        codes.append(code)
    return sorted(codes)


class ExtracteurStage0:
    """Découverte SIRENE-first pilotée par CampaignConfig."""

    def __init__(
        self,
        client: RechercheEntreprisesClient,
        config: CampaignConfig,
    ):
        self.client = client
        self.config = config

    def extraire(self) -> list[LeadStage2]:
        """Exécute la découverte et renvoie la liste plafonnée des LeadStage2."""
        zone = self.config.zone
        if zone.type != "departement":
            raise NotImplementedError(
                f"Stage 0 SIRENE-first : zone type='{zone.type}' non supporté "
                "(seul 'departement' est câblé)."
            )

        filtres = self.config.filtres_entreprise
        tranches = (
            filtres.tranche_effectif_inclus
            or tranches_pour_effectif(filtres.effectif_min, filtres.effectif_max)
        )

        cible = self.config.volume.cible
        # Marge pour absorber dédup + dirigeants/CA manquants éventuels
        max_results = max(cible * 2, cible + 50)

        logger.info(
            "=== Étage 0 — Découverte SIRENE-first ===\n"
            "  Zone : %s  /  NAF : %s  /  Effectif : %s-%s (tranches=%s)\n"
            "  CA : %s-%s  /  Catégorie : %s  /  Cible : %d",
            zone.codes,
            filtres.naf_inclus or "tous",
            filtres.effectif_min, filtres.effectif_max, tranches or "tous",
            filtres.ca_min, filtres.ca_max,
            filtres.categorie_entreprise_inclus or "tous",
            cible,
        )

        leads_par_siren: dict[str, LeadStage2] = {}
        nb_vus = 0
        nb_rejets_mapping = 0

        for entreprise in self.client.decouvrir(
            departements=zone.codes,
            activite_principale=filtres.naf_inclus or None,
            tranche_effectif_salarie=tranches or None,
            ca_min=filtres.ca_min,
            ca_max=filtres.ca_max,
            categorie_entreprise=filtres.categorie_entreprise_inclus or None,
            etat_administratif="A",
            siege_only=True,
            max_results=max_results,
        ):
            nb_vus += 1
            lead = entreprise_to_lead_stage2(
                entreprise,
                secteur_recherche="sirene_decouverte",
                requete_origine=f"dpt={','.join(zone.codes)}",
            )
            if lead is None:
                nb_rejets_mapping += 1
                continue
            if lead.siren in leads_par_siren:
                continue
            leads_par_siren[lead.siren] = lead

            if len(leads_par_siren) >= cible:
                break

        leads = list(leads_par_siren.values())
        logger.info(
            "=== Étage 0 terminé : %d leads (sur %d vus, %d rejets mapping) ===",
            len(leads),
            nb_vus,
            nb_rejets_mapping,
        )
        return leads
