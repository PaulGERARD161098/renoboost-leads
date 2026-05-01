"""Models Pydantic — structures de données du projet.

Chaque étage enrichit progressivement le `Lead` avec ses propres champs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ════════════════════════════════════════════════════════════════
# Configuration YAML
# ════════════════════════════════════════════════════════════════


class RunInfo(BaseModel):
    client_name: str = Field(min_length=1, max_length=80)
    description: str
    campaign_date: str

    @field_validator("client_name")
    @classmethod
    def _slug(cls, v: str) -> str:
        # Pas de caractères "trop bizarres" pour qu'on s'en serve dans des noms de fichier
        forbidden = set("/\\:*?\"<>|")
        if any(c in v for c in forbidden):
            raise ValueError(f"client_name contient des caractères interdits : {forbidden}")
        return v


class StagesFlags(BaseModel):
    enable_stage_1_decouverte: bool = True
    enable_stage_2_entreprises: bool = False
    enable_stage_3_contacts: bool = False
    enable_stage_4_prospection: bool = False


class SecteurCible(BaseModel):
    type: str = Field(
        description="Type Google Places officiel (ex: 'lodging', 'restaurant')"
    )
    query: str = Field(description="Texte de recherche utilisé par Text Search")


class Zone(BaseModel):
    type: Literal["ville", "departement", "region", "france"]
    codes: list[str] = Field(min_length=1)
    rayon_par_point_km: float = Field(default=10.0, gt=0, le=50)
    pas_grille_km: float = Field(default=15.0, gt=0, le=100)


class Filtres(BaseModel):
    statut_requis: Literal["OPERATIONAL", "CLOSED_TEMPORARILY", "tout"] = "OPERATIONAL"
    note_min: float | None = Field(default=None, ge=0, le=5)
    nb_avis_min: int | None = Field(default=None, ge=0)
    nb_avis_max: int | None = Field(default=None, ge=0)
    exiger_telephone: bool = False
    exiger_site_web: bool = False
    dedup_chaines: bool = False


class Volume(BaseModel):
    cible: int = Field(gt=0, le=10_000)
    max_par_secteur: int | None = Field(default=None, ge=1)


class Budget(BaseModel):
    max_eur: float = Field(gt=0, le=1_000)


class Sortie(BaseModel):
    format: list[Literal["csv", "json", "html"]] = ["csv"]
    langue: Literal["fr", "en"] = "fr"


class CampaignConfig(BaseModel):
    """Représente le contenu d'un fichier `config/<client>.yaml`."""

    model_config = ConfigDict(extra="forbid")

    run: RunInfo
    stages: StagesFlags
    secteurs: list[SecteurCible] = Field(min_length=1)
    zone: Zone
    filtres: Filtres = Filtres()
    volume: Volume
    budget: Budget
    sortie: Sortie = Sortie()


# ════════════════════════════════════════════════════════════════
# Lead — structure progressive sur les 4 étages
# ════════════════════════════════════════════════════════════════


class LeadStage1(BaseModel):
    """Données récupérées de Google Places (étage 1)."""

    model_config = ConfigDict(extra="ignore")

    # Identifiants
    place_id: str
    extraction_date: datetime

    # Identité de l'établissement
    nom: str
    adresse: str | None = None
    ville: str | None = None
    code_postal: str | None = None
    pays: str | None = "France"

    # Géolocalisation
    latitude: float | None = None
    longitude: float | None = None

    # Contact
    telephone: str | None = None
    site_web: str | None = None

    # Metrics Google
    note: float | None = None
    nb_avis: int | None = None

    # Catégorisation
    type_principal: str | None = None
    types: list[str] = []
    statut_business: str | None = None
    niveau_prix: int | None = None

    # Sources consultables
    google_maps_url: str | None = None

    # Métadonnées de l'extraction
    secteur_recherche: str | None = None
    requete_origine: str | None = None


# ════════════════════════════════════════════════════════════════
# Stats / résultats d'un run
# ════════════════════════════════════════════════════════════════


class StageStats(BaseModel):
    nom_etage: str
    duree_secondes: float
    nb_appels_api: int
    nb_succes: int
    nb_echecs: int
    cout_eur_estime: float
    leads_collectes: int


class RunStats(BaseModel):
    session_id: str
    campaign: str
    debut: datetime
    fin: datetime | None = None
    duree_totale_secondes: float | None = None
    cout_total_eur: float = 0.0
    etages_executes: list[StageStats] = []
    leads_finaux: int = 0
    erreurs: list[str] = []
