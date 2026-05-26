"""Schéma Pydantic de l'objet `Campagne`.

Une campagne = exécution d'une verticale (l'offre) sur un territoire :
**verticale + zone + volume + budget**. La verticale dit *quoi / à qui*
vendre ; la campagne dit *où, combien, pour quel budget*. Une campagne se
compose en `CampaignConfig` (cf `composer.py`) pour devenir lançable par le
pipeline L1→L4 existant.

Réutilise `Zone`, `Volume`, `Budget` de `models.py` : la forme du territoire,
du volume et du budget est identique à celle d'une campagne classique, seule
l'origine (dérivée d'une verticale) diffère.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models import Budget, Volume, Zone


def _valider_slug(v: str) -> str:
    if not all((c.isalnum() and c.isascii()) or c == "-" for c in v):
        raise ValueError(f"identifiant invalide : '{v}' (attendu : minuscules, chiffres, tirets)")
    if v != v.lower():
        raise ValueError(f"identifiant doit être en minuscules : '{v}'")
    return v


class IdentiteCampagne(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    verticale_slug: str = Field(min_length=1, max_length=80)
    nom: str | None = None
    created: str | None = None  # date ISO YYYY-MM-DD

    @field_validator("id", "verticale_slug")
    @classmethod
    def _slug_format(cls, v: str) -> str:
        return _valider_slug(v)


class Campagne(BaseModel):
    """Contenu validé d'un fichier `campagnes/<id>/campagne.yaml`."""

    model_config = ConfigDict(extra="forbid")

    campagne: IdentiteCampagne
    zone: Zone
    volume: Volume
    budget: Budget

    @property
    def id(self) -> str:
        return self.campagne.id

    @property
    def verticale_slug(self) -> str:
        return self.campagne.verticale_slug
