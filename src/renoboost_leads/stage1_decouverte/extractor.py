"""Extracteur Étage 1 — orchestre la pipeline de découverte.

Pipeline :
1. Génère la grille de points GPS pour la zone
2. Pour chaque (point, secteur) → Text Search (ou Nearby Search si type natif)
3. Pour chaque résultat → mapping vers LeadStage1
4. Dédup par place_id
5. Application des filtres qualité
6. Limitation au volume cible
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..common.budget_guard import BudgetExceededError
from ..common.cache import SessionCache
from ..common.logger import get_logger
from ..models import CampaignConfig, LeadStage1, Zone
from .geo_grid import grille_pour_zone
from .mapper import place_to_lead
from .places_client import PlacesAPIError, PlacesClient

logger = get_logger(__name__)


# Types Places "natifs" : on peut utiliser Nearby Search (plus précis qu'un Text Search)
_TYPES_PLACES_NATIFS = {
    "restaurant",
    "lodging",
    "hospital",
    "supermarket",
    "shopping_mall",
    "movie_theater",
    "bowling_alley",
    "car_dealer",
    "gym",
    "spa",
    "amusement_park",
    "tourist_attraction",
    "event_venue",
}


def _cp_match_departement(cp: str, code_dept: str) -> bool:
    """Vrai si le code postal `cp` (5 chiffres) appartient au département `code_dept`.

    Métropole uniquement. Cas spécial Corse :
    - 2A (Corse-du-Sud) : CP commençant par 200 ou 201
    - 2B (Haute-Corse) : CP commençant par 202..206
    """
    if code_dept == "2A":
        return cp.startswith(("200", "201"))
    if code_dept == "2B":
        return cp[:3] in {"202", "203", "204", "205", "206"}
    return cp.startswith(code_dept)


def lead_dans_zone(lead: LeadStage1, zone: Zone) -> tuple[bool, str]:
    """Vérifie qu'un lead Places appartient bien à la zone cible (filtre B5).

    Stratégie : on compare le `code_postal` extrait par le mapper aux `codes`
    du YAML. Si le CP est absent ou n'appartient à aucun code, on rejette
    (Places retourne parfois des leads voisins du département cible).

    Args:
        lead: Lead issu du mapper Places.
        zone: Configuration zone du YAML (type + codes).

    Returns:
        (accepte, raison_si_rejet) — raison vide en cas d'acceptation.
    """
    # Types autres que 'departement' : pas encore supportés par grille_pour_zone
    # → on ne filtre pas ici (laisse les autres filtres faire leur travail).
    if zone.type != "departement":
        return True, ""

    cp = lead.code_postal
    if not cp or len(cp) != 5 or not cp.isdigit():
        return False, f"hors_zone (cp={cp!r} invalide ou absent)"

    for code in zone.codes:
        if _cp_match_departement(cp, code):
            return True, ""

    return False, f"hors_zone (cp={cp} pas dans {zone.codes})"


def _est_chaine(nom: str) -> str | None:
    """Détecte les enseignes connues (pour dédup_chaines)."""
    n = nom.lower()
    chaines = {
        "carrefour",
        "auchan",
        "leclerc",
        "casino",
        "intermarche",
        "intermarché",
        "lidl",
        "aldi",
        "monoprix",
        "franprix",
        "biocoop",
        "naturalia",
        "ibis",
        "novotel",
        "mercure",
        "accor",
        "kyriad",
        "campanile",
        "best western",
        "holiday inn",
        "marriott",
        "hilton",
        "feu vert",
        "norauto",
        "midas",
        "speedy",
    }
    for marque in chaines:
        if marque in n:
            return marque
    return None


class ExtracteurStage1:
    """Orchestrateur de l'étage 1."""

    def __init__(
        self,
        client: PlacesClient,
        config: CampaignConfig,
        cache: SessionCache | None = None,
    ):
        self.client = client
        self.config = config
        self.cache = cache

    def _passe_filtres(self, lead: LeadStage1) -> tuple[bool, str]:
        """Retourne (passe, raison_si_rejet)."""
        f = self.config.filtres

        # B5 : filtre géographique strict — rejette les leads hors zone.codes
        ok_zone, raison_zone = lead_dans_zone(lead, self.config.zone)
        if not ok_zone:
            return False, raison_zone

        # Statut
        if f.statut_requis != "tout" and lead.statut_business != f.statut_requis:
            return False, f"statut={lead.statut_business} (attendu {f.statut_requis})"

        # Note minimale
        if f.note_min is not None:
            if lead.note is None or lead.note < f.note_min:
                return False, f"note={lead.note} < {f.note_min}"

        # Nombre d'avis
        if f.nb_avis_min is not None:
            if lead.nb_avis is None or lead.nb_avis < f.nb_avis_min:
                return False, f"nb_avis={lead.nb_avis} < {f.nb_avis_min}"
        if f.nb_avis_max is not None:
            if lead.nb_avis is not None and lead.nb_avis > f.nb_avis_max:
                return False, f"nb_avis={lead.nb_avis} > {f.nb_avis_max}"

        # Téléphone obligatoire
        if f.exiger_telephone and not lead.telephone:
            return False, "pas_de_telephone"

        # Site web obligatoire
        if f.exiger_site_web and not lead.site_web:
            return False, "pas_de_site_web"

        return True, ""

    def _executer_recherche(
        self,
        lat: float,
        lng: float,
        rayon_km: float,
        secteur_type: str,
        secteur_query: str,
        cache_key: str,
    ) -> list[dict[str, Any]]:
        """Décide entre Nearby Search et Text Search, et exécute."""
        rayon_metres = int(rayon_km * 1000)

        # Évite l'appel si déjà fait dans la session précédente
        if self.cache and self.cache.search_done(cache_key):
            logger.debug("Recherche déjà effectuée (cache) : %s", cache_key)
            return []

        try:
            if secteur_type in _TYPES_PLACES_NATIFS:
                # Nearby Search : plus précis car par type officiel.
                # Non paginable (l'API Places ne renvoie pas de nextPageToken) :
                # une seule page, `max_pages` est sans effet ici.
                resp = self.client.nearby_search(
                    latitude=lat,
                    longitude=lng,
                    rayon_metres=rayon_metres,
                    included_types=[secteur_type],
                    max_results=20,
                )
                places = resp.get("places", [])
            else:
                # Text Search (fallback) — pagination via nextPageToken jusqu'à
                # `volume.max_pages` (l'API plafonne à 3 pages / ~60 résultats).
                places = []
                page_token: str | None = None
                for _ in range(self.config.volume.max_pages):
                    resp = self.client.text_search(
                        query=secteur_query,
                        latitude=lat,
                        longitude=lng,
                        rayon_metres=rayon_metres,
                        max_results=20,
                        page_token=page_token,
                    )
                    places.extend(resp.get("places", []))
                    page_token = resp.get("nextPageToken")
                    if not page_token:
                        break
        except PlacesAPIError as e:
            logger.warning("Erreur API à %s : %s", cache_key, e)
            return []

        if self.cache:
            self.cache.mark_search_done(cache_key, len(places))

        return places

    def extraire(self) -> list[LeadStage1]:
        """Exécute le pipeline complet de l'étage 1.

        Returns:
            Liste de leads filtrés et dédupliqués.
        """
        logger.info("=== Étage 1 — Découverte ===")
        logger.info(
            "Cible : %d leads sur zone %s=%s",
            self.config.volume.cible,
            self.config.zone.type,
            self.config.zone.codes,
        )

        # 1. Grille géographique
        points = grille_pour_zone(self.config.zone)
        nb_secteurs = len(self.config.secteurs)
        logger.info(
            "Grille générée : %d points × %d secteurs = %d recherches max",
            len(points),
            nb_secteurs,
            len(points) * nb_secteurs,
        )

        # 2. Recherches (boucle sur points × secteurs)
        leads_par_id: dict[str, LeadStage1] = {}
        leads_par_secteur: dict[str, int] = defaultdict(int)
        chaines_vues: set[str] = set()
        nb_rejets = 0
        budget_atteint = False

        try:
            for secteur in self.config.secteurs:
                if budget_atteint:
                    break
                if len(leads_par_id) >= self.config.volume.cible:
                    logger.info("Volume cible atteint, arrêt anticipé")
                    break

                logger.info(
                    "→ Secteur '%s' (type=%s) — début",
                    secteur.query,
                    secteur.type,
                )
                avant = len(leads_par_id)

                for point in points:
                    if len(leads_par_id) >= self.config.volume.cible:
                        break
                    if (
                        self.config.volume.max_par_secteur
                        and leads_par_secteur[secteur.type] >= self.config.volume.max_par_secteur
                    ):
                        break

                    cache_key = (
                        f"{secteur.type}@{point.latitude:.4f},{point.longitude:.4f}"
                        f"_r{point.rayon_km}"
                    )

                    try:
                        places_raw = self._executer_recherche(
                            lat=point.latitude,
                            lng=point.longitude,
                            rayon_km=point.rayon_km,
                            secteur_type=secteur.type,
                            secteur_query=secteur.query,
                            cache_key=cache_key,
                        )
                    except BudgetExceededError as e:
                        logger.error("Budget dépassé : %s", e)
                        budget_atteint = True
                        break

                    # 3. Mapping + filtre + dédup
                    for raw in places_raw:
                        lead = place_to_lead(
                            raw,
                            secteur_recherche=secteur.type,
                            requete_origine=secteur.query,
                        )
                        if lead is None:
                            continue
                        if lead.place_id in leads_par_id:
                            continue

                        # Dédup chaînes (option)
                        if self.config.filtres.dedup_chaines:
                            chaine = _est_chaine(lead.nom)
                            if chaine and chaine in chaines_vues:
                                continue
                            if chaine:
                                chaines_vues.add(chaine)

                        # Filtres qualité
                        ok, raison = self._passe_filtres(lead)
                        if not ok:
                            nb_rejets += 1
                            if raison.startswith("hors_zone"):
                                logger.info(
                                    "Rejet %s : %s (cp=%s, ville=%s)",
                                    lead.nom,
                                    raison,
                                    lead.code_postal,
                                    lead.ville,
                                )
                            continue

                        leads_par_id[lead.place_id] = lead
                        leads_par_secteur[secteur.type] += 1

                logger.info(
                    "  %s : %d nouveaux leads",
                    secteur.query,
                    len(leads_par_id) - avant,
                )

        except KeyboardInterrupt:
            logger.warning("Interruption utilisateur — sauvegarde des leads collectés jusqu'ici")

        leads = list(leads_par_id.values())[: self.config.volume.cible]

        logger.info(
            "=== Étage 1 terminé : %d leads (%d rejets filtres) ===",
            len(leads),
            nb_rejets,
        )

        return leads
