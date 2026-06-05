"""Orchestrateur : combine observations Vision + données IRVE/IGN → 3 scores /10.

`vision` est le dict renvoyé par Claude Vision (cf. worker.satellite). Les surfaces
précises viennent de l'IGN quand disponibles, sinon de l'estimation Vision.
"""

from __future__ import annotations

from typing import Any

from .irve import ClientIRVE, ComptageBornes
from .models import AnalysePotentiels
from .scoring import scorer_bornes, scorer_ombrieres, scorer_solaire

# Ratio de surface réellement exploitable selon le type de toiture (si Vision ne le
# fournit pas) : une toiture plate s'équipe mieux qu'une toiture encombrée.
_RATIO_EXPLOITABLE = {
    "plate": 0.7,
    "inclinee": 0.55,
    "inclinee_nord": 0.45,
    "encombree": 0.4,
    "inconnue": 0.6,
}
_M2_PAR_PLACE = 25.0


def _surface_exploitable(
    surface_toiture: float | None, vision_toit: dict[str, Any]
) -> float | None:
    if not surface_toiture or surface_toiture <= 0:
        return None
    ratio = vision_toit.get("ratio_exploitable")
    if not isinstance(ratio, (int, float)) or not 0 < ratio <= 1:
        ratio = _RATIO_EXPLOITABLE.get((vision_toit.get("type") or "inconnue").lower(), 0.6)
    return round(surface_toiture * ratio, 1)


def _synthese(meilleur: str, analyse: dict[str, int]) -> str:
    libelle = {"solaire": "solaire (toiture)", "ombrieres": "ombrières (parking)",
               "bornes": "bornes de recharge"}[meilleur]
    return f"Meilleur potentiel : {libelle} ({analyse[meilleur]}/10)."


def analyser_potentiels(
    *,
    latitude: float,
    longitude: float,
    vision: dict[str, Any],
    signaux_ve: bool = False,
    irve: ClientIRVE | None = None,
    surface_batie_m2: float | None = None,
    exploitant_probable: str | None = None,
    image_url: str | None = None,
    analyzed_at: str | None = None,
) -> AnalysePotentiels:
    toit = vision.get("toiture") or {}
    park = vision.get("parking") or {}

    # --- Solaire ---
    surface_toiture = surface_batie_m2 or toit.get("surface_estimee_m2")
    surface_toiture = surface_toiture if isinstance(surface_toiture, (int, float)) else None
    exploitable = _surface_exploitable(surface_toiture, toit) if toit.get("presente") else None
    solaire = scorer_solaire(
        surface_exploitable_m2=exploitable,
        surface_toiture_m2=surface_toiture,
        type_toiture=toit.get("type"),
    )

    # --- Ombrières ---
    surface_parking = park.get("surface_estimee_m2")
    surface_parking = surface_parking if isinstance(surface_parking, (int, float)) else None
    nb_places = park.get("nb_places_estime")
    if not isinstance(nb_places, int) and surface_parking:
        nb_places = int(surface_parking / _M2_PAR_PLACE)
    ombrieres = scorer_ombrieres(
        parking_present=bool(park.get("present")),
        nb_places=nb_places if isinstance(nb_places, int) else None,
        surface_parking_m2=surface_parking,
        partage=park.get("partage"),
        exploitant_probable=exploitant_probable,
    )

    # --- Bornes ---
    comptage = irve.compter(latitude, longitude) if irve else ComptageBornes()
    bornes_vues = vision.get("bornes_visibles")
    sur_site = comptage.sur_site
    if isinstance(bornes_vues, int) and bornes_vues > sur_site:
        sur_site = bornes_vues  # le dataset IRVE peut être incomplet
    bornes = scorer_bornes(
        sur_site=sur_site,
        voisinage_1km=comptage.voisinage_1km,
        rayon_10km=comptage.rayon_10km,
        signaux_ve=signaux_ve,
        types=comptage.types,
    )

    scores = {"solaire": solaire.score, "ombrieres": ombrieres.score, "bornes": bornes.score}
    meilleur = max(scores, key=lambda k: scores[k])
    return AnalysePotentiels(
        solaire=solaire,
        ombrieres=ombrieres,
        bornes=bornes,
        meilleur=meilleur,
        synthese=_synthese(meilleur, scores),
        image_url=image_url,
        analyzed_at=analyzed_at,
    )


__all__ = ["analyser_potentiels"]
