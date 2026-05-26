"""Schéma Pydantic de l'objet `Verticale`.

Une verticale encapsule l'offre commerciale d'un client professionnel
utilisateur de l'outil : offre + cibles + signaux + qualification + ton mail
+ séquence. C'est l'unité pivotable du produit (cf VERTICALES.md).

Réutilise `SecteurCible` et `FiltresEntreprise` de `models.py` : la forme des
cibles d'une verticale est identique à celle d'une campagne, seule la
composition (zone/volume/budget) diffère et reste portée par `CampaignConfig`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models import FiltresEntreprise, SecteurCible

# V0 : seul `b2b` est exploitable. Le modèle connaît `b2c-particulier` pour
# préparer la V1, mais le loader le refuse (cf loader.VerticaleHorsV0Error).
CibleType = Literal["b2b", "b2c-particulier"]


class Identite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=1, max_length=80)
    nom: str = Field(min_length=1)
    description: str = Field(min_length=1)

    @field_validator("slug")
    @classmethod
    def _slug_format(cls, v: str) -> str:
        if not all(c.isalnum() and c.isascii() or c == "-" for c in v):
            raise ValueError(
                f"slug invalide : '{v}' (attendu : minuscules, chiffres et tirets)"
            )
        if v != v.lower():
            raise ValueError(f"slug doit être en minuscules : '{v}'")
        return v


class Cible(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: CibleType
    detail: str = Field(min_length=1)


class Offre(BaseModel):
    model_config = ConfigDict(extra="forbid")

    produit: str = Field(min_length=1)
    argument_principal: str = Field(min_length=1)
    ticket_moyen_eur: int = Field(gt=0)


class Cibles(BaseModel):
    model_config = ConfigDict(extra="forbid")

    secteurs_places: list[SecteurCible] = Field(min_length=1)
    filtres_entreprise: FiltresEntreprise = Field(default_factory=FiltresEntreprise)


class Qualification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seuil_score_top: int = Field(ge=0, le=100)
    criteres_top: list[str] = Field(min_length=1)
    criteres_exclusion: list[str] = Field(default_factory=list)


class Enrichissements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    l3_5_dropcontact: bool = True
    lecture_site_web: bool = True
    detection_terrain: bool = False  # V1


class TonMail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registre: str = Field(min_length=1)
    longueur_mots: int = Field(gt=0, le=1000)
    attaque: str = Field(min_length=1)
    cta: str = Field(min_length=1)
    signaux_a_personnaliser: list[str] = Field(default_factory=list)


class EtapeSequence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template: str = Field(min_length=1)
    sujet: str = Field(min_length=1)


class Sequence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    j0: EtapeSequence
    j3: EtapeSequence | None = None
    j7: EtapeSequence | None = None


class BudgetTypique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    volume_cible: int = Field(gt=0)
    cout_pipeline_eur: float = Field(ge=0)
    cout_avec_l3_5_eur: float = Field(ge=0)


class Verticale(BaseModel):
    """Contenu validé d'un fichier `verticales/<slug>/verticale.yaml`."""

    model_config = ConfigDict(extra="forbid")

    verticale: Identite
    cible: Cible
    offre: Offre
    cibles: Cibles
    signaux: list[str] = Field(min_length=1)
    qualification: Qualification
    enrichissements: Enrichissements = Field(default_factory=Enrichissements)
    ton_mail: TonMail
    sequence: Sequence
    budget_typique: BudgetTypique

    @property
    def slug(self) -> str:
        return self.verticale.slug
