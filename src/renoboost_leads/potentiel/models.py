"""Modèles de l'analyse de potentiel (3 potentiels notés /10 + synthèse)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


def niveau_pour_score(score: int) -> str:
    """Étiquette lisible à partir d'un score /10."""
    if score >= 7:
        return "Fort"
    if score >= 4:
        return "Moyen"
    if score >= 1:
        return "Faible"
    return "Nul"


class PotentielSolaire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int = Field(ge=0, le=10)
    niveau: str
    surface_toiture_m2: float | None = None
    surface_exploitable_m2: float | None = None
    type_toiture: str | None = None  # plate | inclinee | inclinee_nord | encombree | inconnue
    justification: str = ""


class PotentielOmbrieres(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int = Field(ge=0, le=10)
    niveau: str
    surface_parking_m2: float | None = None
    nb_places: int | None = None
    partage: bool | None = None  # parking partagé entre plusieurs occupants
    exploitant_probable: str | None = None
    justification: str = ""


class PotentielBornes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int = Field(ge=0, le=10)
    niveau: str
    sur_site: int = 0  # bornes détectées sur le site même (~150 m)
    voisinage_1km: int = 0
    rayon_10km: int = 0
    types: list[str] = Field(default_factory=list)  # ex. ["22 kW AC", "150 kW DC"]
    justification: str = ""


class AnalysePotentiels(BaseModel):
    """Résultat consolidé de l'analyse des 3 potentiels d'un prospect."""

    model_config = ConfigDict(extra="forbid")

    version: int = 2
    solaire: PotentielSolaire
    ombrieres: PotentielOmbrieres
    bornes: PotentielBornes
    meilleur: str  # "solaire" | "ombrieres" | "bornes"
    synthese: str = ""
    image_url: str | None = None
    analyzed_at: str | None = None

    @property
    def score_max(self) -> int:
        return max(self.solaire.score, self.ombrieres.score, self.bornes.score)


__all__ = [
    "AnalysePotentiels",
    "PotentielBornes",
    "PotentielOmbrieres",
    "PotentielSolaire",
    "niveau_pour_score",
]
