"""Mapper : réponse API recherche-entreprises → LeadStage2.

L'API renvoie déjà toutes les données identité + finances + dirigeants, donc
on saute l'étape LeadStage1 (Google Places) et on produit directement un
LeadStage2 prêt pour l'étage 3 (scraping).

Le `place_id` est un sentinel `sirene:<siren>` car aucun place_id Google n'a
été récupéré à ce stade. Si le pipeline aval (mode hybride) enrichit ensuite
avec Places, le vrai place_id remplacera le sentinel.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..common.logger import get_logger
from ..common.naf import libelle_naf_pour_code
from ..models import LeadStage2

logger = get_logger(__name__)


def _premier_dirigeant_physique(dirigeants: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Renvoie le premier dirigeant personne physique (nom + prénom) trouvé."""
    for d in dirigeants or []:
        if d.get("type_dirigeant") == "personne physique" or (d.get("nom") and d.get("prenom")):
            return d
    return None


def _derniere_annee_finances(finances: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    """Renvoie (année, dict) pour la dernière année dispo, sinon (None, {})."""
    if not finances:
        return None, {}
    annees = sorted(finances.keys(), reverse=True)
    if not annees:
        return None, {}
    annee = annees[0]
    return annee, finances.get(annee, {}) or {}


def entreprise_to_lead_stage2(
    entreprise: dict[str, Any],
    *,
    secteur_recherche: str = "sirene_decouverte",
    requete_origine: str | None = None,
) -> LeadStage2 | None:
    """Convertit une entreprise renvoyée par recherche-entreprises en LeadStage2.

    Args:
        entreprise: dict brut renvoyé par l'API.
        secteur_recherche: étiquette tracée dans le lead pour les statistiques.
        requete_origine: chaîne décrivant les filtres ayant produit le lead.

    Returns:
        LeadStage2 prêt pour l'étage 3, ou None si données minimales manquantes.
    """
    siren = entreprise.get("siren")
    nom = entreprise.get("nom_complet") or entreprise.get("nom_raison_sociale")
    if not siren or not nom:
        logger.debug("Entreprise rejetée (siren ou nom manquant) : %s", siren)
        return None

    siege = entreprise.get("siege") or {}
    finances = entreprise.get("finances") or {}
    dirigeants = entreprise.get("dirigeants") or []

    annee_fin, fin = _derniere_annee_finances(finances)
    dirigeant = _premier_dirigeant_physique(dirigeants) or {}

    etat = entreprise.get("etat_administratif")
    statut_business = "OPERATIONAL" if etat == "A" else "CLOSED"

    # L'API renvoie latitude/longitude au siège, mais aussi un champ
    # "coordonnees" formaté "lat,lng". On préfère les champs typés.
    lat = siege.get("latitude")
    lng = siege.get("longitude")
    try:
        lat = float(lat) if lat is not None else None
        lng = float(lng) if lng is not None else None
    except (TypeError, ValueError):
        lat, lng = None, None

    return LeadStage2(
        # Identifiants
        place_id=f"sirene:{siren}",
        extraction_date=datetime.now(timezone.utc),

        # Identité (couches LeadStage1)
        nom=nom,
        adresse=siege.get("geo_adresse") or siege.get("adresse"),
        ville=siege.get("libelle_commune") or siege.get("commune"),
        code_postal=siege.get("code_postal"),
        pays="France",
        latitude=lat,
        longitude=lng,
        telephone=None,
        site_web=None,
        note=None,
        nb_avis=None,
        type_principal=entreprise.get("activite_principale"),
        types=[],
        statut_business=statut_business,
        niveau_prix=None,
        google_maps_url=None,
        secteur_recherche=secteur_recherche,
        requete_origine=requete_origine,

        # Champs LeadStage2
        siren=siren,
        siret=siege.get("siret"),
        code_naf=siege.get("activite_principale") or entreprise.get("activite_principale"),
        libelle_naf=(
            entreprise.get("libelle_activite_principale")
            or siege.get("libelle_activite_principale")
            # Repli local (l'API ne renvoie pas toujours le libellé).
            or libelle_naf_pour_code(
                siege.get("activite_principale") or entreprise.get("activite_principale")
            )
        ),
        forme_juridique=entreprise.get("nature_juridique"),  # code INSEE
        statut_actif=(etat == "A"),
        tranche_effectif=entreprise.get("tranche_effectif_salarie"),
        libelle_effectif=(
            entreprise.get("libelle_tranche_effectif_salarie")
            or siege.get("libelle_tranche_effectif_salarie")
        ),
        dirigeant_nom=dirigeant.get("nom"),
        dirigeant_prenom=dirigeant.get("prenom"),
        dirigeant_qualite=dirigeant.get("qualite"),
        adresse_normalisee=siege.get("geo_adresse"),
        date_creation=entreprise.get("date_creation"),
        nb_etablissements=entreprise.get("nombre_etablissements"),
        chiffre_affaires=fin.get("ca"),
        resultat_net=fin.get("resultat_net"),
        annee_finances=annee_fin,
        categorie_entreprise=entreprise.get("categorie_entreprise"),
        # Match SIRENE-first = direct, pas de matching par nom
        score_matching=100.0,
        match_incertain=False,
        flag_chaine=False,
        note_chaine=None,
        hors_filtre_entreprise=False,
        raison_hors_filtre=None,
    )
