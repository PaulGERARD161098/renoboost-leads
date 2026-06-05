"""Scoring /10 des 3 potentiels — logique pure (aucun réseau), entièrement testable.

Barèmes validés avec le client (calibration du 2026-06) :

SOLAIRE (sur la surface EXPLOITABLE de toiture)
  base : ≥1500→10 · 800-1500→7 · 300-800→4 · <300→1 · 0/absente→0
  type : plate +2 · inclinée nord/encombrée −2 · sinon 0          (clamp 0-10)

OMBRIÈRES (sur le nombre de places)
  base : ≥150→10 · 60-150→7 · 20-60→4 · <20→1 · pas de parking→0
  dédié +2 · partagé −3                                            (clamp 0-10)

BORNES (« les deux » : adoption de la zone + manque sur site)
  adoption (0-6) : voisins<1km OU signaux VE +3 · 1-9 bornes <10km +2 ·
                   ≥10 bornes <10km +3   (plafond 6)
  manque (0-4)   : 0 borne sur site +4 · déjà équipé +1
  score = adoption + manque                                        (clamp 0-10)
"""

from __future__ import annotations

from .models import (
    PotentielBornes,
    PotentielOmbrieres,
    PotentielSolaire,
    niveau_pour_score,
)


def _clamp10(x: int) -> int:
    return max(0, min(10, x))


def scorer_solaire(
    *,
    surface_exploitable_m2: float | None,
    surface_toiture_m2: float | None = None,
    type_toiture: str | None = None,
) -> PotentielSolaire:
    expl = surface_exploitable_m2
    if not expl or expl <= 0:
        base = 0
    elif expl >= 1500:
        base = 10
    elif expl >= 800:
        base = 7
    elif expl >= 300:
        base = 4
    else:
        base = 1

    bonus = 0
    t = (type_toiture or "").lower()
    if base > 0:
        if t == "plate":
            bonus = 2
        elif t in ("inclinee_nord", "encombree"):
            bonus = -2
    score = _clamp10(base + bonus)

    if base == 0:
        just = "Pas de toiture exploitable détectée."
    else:
        det = f"~{int(expl)} m² exploitables" if expl else "surface estimée"
        ttxt = {"plate": "toiture plate", "inclinee": "toiture inclinée",
                "inclinee_nord": "toiture inclinée nord", "encombree": "toiture encombrée"}.get(
                    t, "type indéterminé")
        just = f"{det}, {ttxt}."
    return PotentielSolaire(
        score=score,
        niveau=niveau_pour_score(score),
        surface_toiture_m2=surface_toiture_m2,
        surface_exploitable_m2=expl,
        type_toiture=type_toiture,
        justification=just,
    )


def scorer_ombrieres(
    *,
    parking_present: bool,
    nb_places: int | None,
    surface_parking_m2: float | None = None,
    partage: bool | None = None,
    exploitant_probable: str | None = None,
) -> PotentielOmbrieres:
    places = nb_places or 0
    if not parking_present or places <= 0:
        base = 0
    elif places >= 150:
        base = 10
    elif places >= 60:
        base = 7
    elif places >= 20:
        base = 4
    else:
        base = 1

    bonus = 0
    if base > 0 and partage is not None:
        bonus = -3 if partage else 2
    score = _clamp10(base + bonus)

    if base == 0:
        just = "Pas de parking exploitable détecté."
    else:
        part = "partagé" if partage else ("dédié" if partage is False else "usage indéterminé")
        just = f"~{places} places, parking {part}."
    return PotentielOmbrieres(
        score=score,
        niveau=niveau_pour_score(score),
        surface_parking_m2=surface_parking_m2,
        nb_places=nb_places,
        partage=partage,
        exploitant_probable=exploitant_probable,
        justification=just,
    )


def scorer_bornes(
    *,
    sur_site: int,
    voisinage_1km: int,
    rayon_10km: int,
    signaux_ve: bool = False,
    types: list[str] | None = None,
) -> PotentielBornes:
    adoption = 0
    if voisinage_1km > 0 or signaux_ve:
        adoption += 3
    if rayon_10km >= 10:
        adoption += 3
    elif rayon_10km >= 1:
        adoption += 2
    adoption = min(6, adoption)

    manque = 4 if sur_site == 0 else 1
    score = _clamp10(adoption + manque)

    if sur_site > 0:
        just = f"Déjà {sur_site} borne(s) sur site ; "
    else:
        just = "Aucune borne sur site ; "
    if voisinage_1km > 0 or signaux_ve:
        just += "zone qui s'électrifie (voisinage / signaux VE)."
    elif rayon_10km > 0:
        just += f"{rayon_10km} borne(s) dans un rayon de 10 km."
    else:
        just += "peu d'infrastructure de recharge alentour."
    return PotentielBornes(
        score=score,
        niveau=niveau_pour_score(score),
        sur_site=sur_site,
        voisinage_1km=voisinage_1km,
        rayon_10km=rayon_10km,
        types=types or [],
        justification=just,
    )


__all__ = ["scorer_bornes", "scorer_ombrieres", "scorer_solaire"]
