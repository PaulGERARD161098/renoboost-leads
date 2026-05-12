"""Models Pydantic — structures de données du projet.

Chaque étage enrichit progressivement le `Lead` avec ses propres champs.
Les modèles suivent une logique d'extension : LeadStage2 hérite/contient LeadStage1, etc.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ════════════════════════════════════════════════════════════════
# Configuration YAML (campagne)
# ════════════════════════════════════════════════════════════════


class RunInfo(BaseModel):
    client_name: str = Field(min_length=1, max_length=80)
    description: str
    campaign_date: str

    @field_validator("client_name")
    @classmethod
    def _slug(cls, v: str) -> str:
        forbidden = set('/\\:*?"<>|')
        if any(c in v for c in forbidden):
            raise ValueError(f"client_name contient des caractères interdits : {forbidden}")
        return v


class StagesFlags(BaseModel):
    enable_stage_1_decouverte: bool = True
    enable_stage_2_entreprises: bool = False
    enable_stage_3_contacts: bool = False
    enable_stage_4_prospection: bool = False


class SecteurCible(BaseModel):
    type: str = Field(description="Type Google Places officiel (ex: 'lodging', 'restaurant')")
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


class FiltresEntreprise(BaseModel):
    """Filtres appliqués après l'étage 2 (données entreprise enrichies).

    Comportement : les leads qui ne passent pas les filtres ne sont PAS rejetés.
    Ils sont flagués (`hors_filtre_entreprise=True` + `raison_hors_filtre`) puis
    exportés séparément en sortie L3 pour éviter le mélange avec les leads
    qualifiés. L3 (scraping/patterns) est exécuté sur les deux populations.
    """

    model_config = ConfigDict(extra="forbid")

    # Effectif : double interface
    # - effectif_min/max : nombre de salariés, user-friendly (default si seul fourni)
    # - tranche_effectif_inclus : codes INSEE bruts ex ["21","22","31"], précis
    #   et prioritaire si fourni.
    effectif_min: int | None = Field(default=None, ge=0)
    effectif_max: int | None = Field(default=None, ge=0)
    tranche_effectif_inclus: list[str] = Field(default_factory=list)

    # NAF : préfixe libre. "25" matche "25.62A" ; "25.62A" ne matche que ce code.
    naf_inclus: list[str] = Field(default_factory=list)
    naf_exclus: list[str] = Field(default_factory=list)

    # Forme juridique : labels (SAS, SARL, ...) ou codes INSEE bruts (5710, ...)
    forme_juridique_inclus: list[str] = Field(default_factory=list)
    forme_juridique_exclus: list[str] = Field(default_factory=list)

    # Sites
    multi_sites_only: bool = False


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
    filtres_entreprise: FiltresEntreprise = Field(default_factory=FiltresEntreprise)
    volume: Volume
    budget: Budget
    sortie: Sortie = Sortie()


# ════════════════════════════════════════════════════════════════
# ÉTAGE 1 — Données Google Places
# ════════════════════════════════════════════════════════════════


class LeadStage1(BaseModel):
    """Données récupérées de Google Places (étage 1)."""

    model_config = ConfigDict(extra="ignore")

    place_id: str
    extraction_date: datetime

    # Identité
    nom: str
    adresse: str | None = None
    ville: str | None = None
    code_postal: str | None = None
    pays: str | None = "France"

    # Géoloc
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

    # Sources
    google_maps_url: str | None = None

    # Métadonnées
    secteur_recherche: str | None = None
    requete_origine: str | None = None


# ════════════════════════════════════════════════════════════════
# ÉTAGE 2 — Données entreprise (data.gouv.fr)
# ════════════════════════════════════════════════════════════════


class LeadStage2(LeadStage1):
    """LeadStage1 + colonnes enrichies via API recherche-entreprises.api.gouv.fr."""

    # SIREN / SIRET
    siren: str | None = None
    siret: str | None = None

    # NAF / catégorie
    code_naf: str | None = None
    libelle_naf: str | None = None

    # Forme juridique & statut
    forme_juridique: str | None = None
    statut_actif: bool | None = None

    # Effectif (tranche INSEE)
    tranche_effectif: str | None = None
    libelle_effectif: str | None = None

    # Dirigeant principal
    dirigeant_nom: str | None = None
    dirigeant_prenom: str | None = None
    dirigeant_qualite: str | None = None  # ex: "Président", "Gérant"

    # Adresse normalisée (depuis Sirene)
    adresse_normalisee: str | None = None

    # Date de création
    date_creation: str | None = None  # format YYYY-MM-DD

    # Nombre d'établissements de l'unité légale (multi-sites)
    nb_etablissements: int | None = None

    # Métadonnées de matching
    score_matching: float | None = None  # 0-100
    match_incertain: bool = False  # True si score < 60
    flag_chaine: bool = False  # True si Accor / Carrefour / etc.
    note_chaine: str | None = None  # "Lead à enrichir manuellement via siège"

    # Filtres entreprise (Bloc 3) — flag posé après application des filtres YAML
    hors_filtre_entreprise: bool = False
    raison_hors_filtre: str | None = None


# ════════════════════════════════════════════════════════════════
# ÉTAGE 3 — Contacts (scraping + patterns)
# ════════════════════════════════════════════════════════════════


class LeadStage3(LeadStage2):
    """LeadStage2 + emails (scrapés et patterns générés)."""

    # Emails issus du scraping (présumés valides car publiés sur le site)
    emails_verifies: list[str] = []  # emails effectivement scrapés

    # Emails générés par patterns (à vérifier avant envoi)
    emails_candidats: list[str] = []  # patterns générés

    # Métadonnées
    domaine_extrait: str | None = None  # ex: "hotellesud.fr"
    page_source_emails: str | None = None  # URL où les emails ont été trouvés
    nb_emails_verifies: int = 0
    nb_emails_candidats: int = 0
    source_globale: Literal[
        "scraping_uniquement",
        "patterns_uniquement",
        "scraping_et_patterns",
        "aucun_email",
        "chaine_non_traitee",
    ] = "aucun_email"
    contient_dirigeant_pattern: bool = False  # True si patterns nominatifs générés


# ════════════════════════════════════════════════════════════════
# Stats & résultats du run
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
