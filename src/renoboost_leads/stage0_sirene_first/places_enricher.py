"""Enrichissement Places ciblé en mode SIRENE-first.

Pour chaque LeadStage2 produit par l'extracteur SIRENE-first, on lance UN
appel `text_search` Places sur "{nom} {ville}" pour récupérer site_web,
téléphone, note Google. La ville Places doit matcher la ville SIRENE,
sinon on ignore (Places aurait pu renvoyer un homonyme d'une autre région).

Si Places renvoie 0 résultat, erreur API, ou ville incohérente, le lead
sort inchangé (place_id reste le sentinel `sirene:<siren>`, site_web reste
None — stage3 ne pourra pas scraper mais le lead reste exportable).
"""

from __future__ import annotations

from ..common.budget_guard import BudgetExceededError
from ..common.logger import get_logger
from ..models import LeadStage2
from ..stage1_decouverte.mapper import place_to_lead
from ..stage1_decouverte.places_client import PlacesAPIError, PlacesClient

logger = get_logger(__name__)


def _normaliser_ville(v: str) -> str:
    """Compare-friendly : lowercase, retire tirets/apostrophes/espaces multiples."""
    return " ".join(v.lower().replace("-", " ").replace("'", " ").split())


def villes_correspondent(v1: str | None, v2: str | None) -> bool:
    """Match permissif : strict ou inclusion (ex 'Lille' vs 'Lille Métropole')."""
    if not v1 or not v2:
        return False
    n1, n2 = _normaliser_ville(v1), _normaliser_ville(v2)
    return n1 == n2 or n1 in n2 or n2 in n1


class EnrichisseurPlaces:
    """Ajoute les champs Places à un LeadStage2 SIRENE-first (best effort)."""

    def __init__(self, client: PlacesClient):
        self.client = client

    def enrichir(self, lead: LeadStage2) -> LeadStage2:
        """Renvoie un lead enrichi si Places match, sinon le lead inchangé.

        Lève BudgetExceededError (le caller orchestre l'arrêt de pipeline).
        """
        if not lead.nom:
            return lead
        query = f"{lead.nom} {lead.ville or ''}".strip()

        try:
            resp = self.client.text_search(query=query, max_results=1)
        except BudgetExceededError:
            raise
        except PlacesAPIError as e:
            logger.warning("Places enrichissement erreur API pour %s : %s", lead.nom, e)
            return lead

        places = resp.get("places") or []
        if not places:
            return lead

        lead_places = place_to_lead(
            places[0],
            secteur_recherche="enrichissement_sirene",
            requete_origine=query,
        )
        if lead_places is None:
            return lead

        # Garde-fou : la ville Places doit matcher la ville SIRENE pour
        # éviter de récupérer un homonyme à l'autre bout de la France.
        if lead.ville and lead_places.ville and not villes_correspondent(lead.ville, lead_places.ville):
            logger.debug(
                "Mismatch ville pour %s : sirene=%s places=%s — pas d'enrichissement",
                lead.nom, lead.ville, lead_places.ville,
            )
            return lead

        return lead.model_copy(update={
            "place_id": lead_places.place_id,
            "telephone": lead_places.telephone or lead.telephone,
            "site_web": lead_places.site_web or lead.site_web,
            "note": lead_places.note,
            "nb_avis": lead_places.nb_avis,
            "google_maps_url": lead_places.google_maps_url,
            "type_principal": lead_places.type_principal or lead.type_principal,
            "types": lead_places.types or lead.types,
        })

    def enrichir_lot(self, leads: list[LeadStage2]) -> list[LeadStage2]:
        """Enrichit chaque lead. Stoppe net si BudgetExceededError."""
        sortie: list[LeadStage2] = []
        for lead in leads:
            try:
                sortie.append(self.enrichir(lead))
            except BudgetExceededError as e:
                logger.error("Budget Places dépassé en cours d'enrichissement : %s", e)
                # On garde tous les leads déjà enrichis + ceux pas encore traités
                # (sans place_id Places — ils restent exploitables hors-scraping).
                sortie.extend(leads[len(sortie):])
                break
        return sortie
