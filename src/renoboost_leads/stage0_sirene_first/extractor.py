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
from ..stage2_entreprises.filters import (
    _TRANCHES_INSEE,
    _match_naf_prefixe,
    evaluer_filtres_entreprise,
)
from ..stage2_entreprises.recherche_client import (
    RechercheEntreprisesClient,
    RechercheEntreprisesTransientError,
)
from .geocoder import BANGeocoder
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
        geocoder: BANGeocoder | None = None,
    ):
        self.client = client
        self.config = config
        # Géocodeur optionnel : requis uniquement si zone='point' est définie
        # par une adresse en clair (sans latitude/longitude).
        self.geocoder = geocoder

    def _resoudre_centre(self) -> tuple[float, float]:
        """Renvoie (latitude, longitude) du centre en mode zone='point'.

        Utilise les coordonnées si fournies, sinon géocode l'adresse via la BAN.
        """
        zone = self.config.zone
        if zone.latitude is not None and zone.longitude is not None:
            return zone.latitude, zone.longitude
        if not zone.adresse:
            raise ValueError(
                "zone='point' sans coordonnées ni adresse — configuration invalide."
            )
        if self.geocoder is None:
            raise ValueError(
                "zone='point' définie par adresse mais aucun géocodeur fourni "
                "à l'extracteur."
            )
        res = self.geocoder.geocoder(zone.adresse)
        return res.latitude, res.longitude

    def extraire(self) -> list[LeadStage2]:
        """Exécute la découverte et renvoie la liste plafonnée des LeadStage2."""
        zone = self.config.zone
        if zone.type not in ("departement", "point"):
            raise NotImplementedError(
                f"Stage 0 SIRENE-first : zone type='{zone.type}' non supporté "
                "(seuls 'departement' et 'point' sont câblés)."
            )

        filtres = self.config.filtres_entreprise
        tranches = (
            filtres.tranche_effectif_inclus
            or tranches_pour_effectif(filtres.effectif_min, filtres.effectif_max)
        )

        cible = self.config.volume.cible
        # Marge pour absorber dédup + dirigeants/CA manquants éventuels
        max_results = max(cible * 2, cible + 50)

        centre_lat: float | None = None
        centre_lon: float | None = None
        if zone.type == "point":
            centre_lat, centre_lon = self._resoudre_centre()
            origine = zone.adresse or f"{centre_lat},{centre_lon}"
            zone_label = f"point=({centre_lat},{centre_lon}) r={zone.rayon_par_point_km}km"
            requete_origine = f"point={origine}"
        else:
            zone_label = ",".join(zone.codes)
            requete_origine = f"dpt={zone_label}"

        logger.info(
            "=== Étage 0 — Découverte SIRENE-first ===\n"
            "  Zone : %s  /  NAF : %s  /  Effectif : %s-%s (tranches=%s)\n"
            "  CA : %s-%s  /  Catégorie : %s  /  Cible : %d",
            zone_label,
            filtres.naf_inclus or "tous",
            filtres.effectif_min, filtres.effectif_max, tranches or "tous",
            filtres.ca_min, filtres.ca_max,
            filtres.categorie_entreprise_inclus or "tous",
            cible,
        )

        leads_par_siren: dict[str, LeadStage2] = {}
        nb_vus = 0
        nb_rejets_mapping = 0
        nb_hors_naf = 0
        nb_hors_filtre = 0
        coupure_api = False

        # On itère sur le générateur dans un try/except pour qu'une coupure
        # API en cours de pagination préserve les leads déjà collectés.
        if zone.type == "point":
            iterateur = self.client.decouvrir_near_point(
                latitude=centre_lat,
                longitude=centre_lon,
                radius_km=zone.rayon_par_point_km,
                activite_principale=filtres.naf_inclus or None,
                tranche_effectif_salarie=tranches or None,
                ca_min=filtres.ca_min,
                ca_max=filtres.ca_max,
                categorie_entreprise=filtres.categorie_entreprise_inclus or None,
                etat_administratif="A",
                siege_only=True,
                max_results=max_results,
            )
        else:
            iterateur = self.client.decouvrir(
                departements=zone.codes,
                activite_principale=filtres.naf_inclus or None,
                tranche_effectif_salarie=tranches or None,
                ca_min=filtres.ca_min,
                ca_max=filtres.ca_max,
                categorie_entreprise=filtres.categorie_entreprise_inclus or None,
                etat_administratif="A",
                siege_only=True,
                max_results=max_results,
            )

        try:
            for entreprise in iterateur:
                nb_vus += 1
                lead = entreprise_to_lead_stage2(
                    entreprise,
                    secteur_recherche="sirene_decouverte",
                    requete_origine=requete_origine,
                )
                if lead is None:
                    nb_rejets_mapping += 1
                    continue
                if lead.siren in leads_par_siren:
                    continue
                # Resserrage NAF : la cible naf_inclus a pu être élargie à la
                # SECTION pour l'appel API (les divisions/préfixes ne sont pas
                # acceptés en activite_principale). On exclut ici les entreprises
                # de la section qui ne matchent pas le préfixe exact — réplique le
                # pré-filtrage NAF que l'API faisait avec des codes complets.
                # No-op quand la cible était déjà en codes complets.
                if filtres.naf_inclus and not _match_naf_prefixe(
                    lead.code_naf, filtres.naf_inclus
                ):
                    nb_hors_naf += 1
                    continue
                # Filtres entreprise (NAF/forme juridique/CA/effectif/…) :
                # flag-not-drop, comme l'enricher L2. Sans ça, naf_exclus &
                # consorts n'auraient aucun effet en mode SIRENE-first.
                passe, raison = evaluer_filtres_entreprise(lead, filtres)
                if not passe:
                    lead.hors_filtre_entreprise = True
                    lead.raison_hors_filtre = raison
                    nb_hors_filtre += 1
                leads_par_siren[lead.siren] = lead

                if len(leads_par_siren) >= cible:
                    break
        except RechercheEntreprisesTransientError as e:
            coupure_api = True
            logger.warning(
                "API recherche-entreprises indisponible (retries épuisés) : %s — "
                "on continue avec les %d leads déjà collectés.",
                e, len(leads_par_siren),
            )

        leads = list(leads_par_siren.values())
        logger.info(
            "=== Étage 0 terminé : %d leads (dont %d hors-filtre) "
            "sur %d vus, %d hors-NAF, %d rejets mapping%s ===",
            len(leads),
            nb_hors_filtre,
            nb_vus,
            nb_hors_naf,
            nb_rejets_mapping,
            ", coupure API" if coupure_api else "",
        )
        return leads
