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
    enable_stage_3_5_enrichment: bool = False
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
    # Effectif inconnu (tranche absente, fréquent sur établissements secondaires
    # Sirene) : par défaut on n'évince PAS, sinon le filtre mange tous ces leads.
    rejeter_effectif_inconnu: bool = False

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


class EnrichissementL35(BaseModel):
    """Configuration de l'étage 3.5 (enrichissement Dropcontact).

    Étage optionnel placé entre L3 (scraping/patterns) et L4 (scoring Claude).
    Appelle l'API Dropcontact pour enrichir les leads avec :
    - Email vérifié du dirigeant (qualification SMTP côté Dropcontact)
    - Téléphone direct (si disponible)
    - URL LinkedIn dirigeant
    - Civilité / prénom / nom normalisés

    Coût indicatif : ~0.5 €/lead enrichi (plan Starter Dropcontact).
    Filtre intelligent : seuls les leads passant les filtres entreprise
    (`hors_filtre_entreprise=False`) sont envoyés à l'API.
    """

    model_config = ConfigDict(extra="forbid")

    # Provider (extensible : kaspr, hunter, ... plus tard)
    provider: Literal["dropcontact"] = "dropcontact"

    # Langue pour le prompt Dropcontact ("fr" / "en")
    language: Literal["fr", "en"] = "fr"

    # Demande la vérification SIREN par Dropcontact (recommandé pour FR)
    siren: bool = True

    # Taille max d'un lot envoyé à l'API (Dropcontact recommande ≤ 250)
    batch_size: int = Field(default=50, ge=1, le=250)

    # Polling : délai d'attente initial puis intervalle entre 2 polls (secondes)
    poll_initial_delay_s: float = Field(default=10.0, ge=1.0, le=120.0)
    poll_interval_s: float = Field(default=10.0, ge=1.0, le=60.0)
    poll_timeout_s: float = Field(default=600.0, ge=30.0, le=3600.0)

    # Coût indicatif par lead enrichi (€). Sert au budget guard et aux stats.
    cout_par_lead_eur: float = Field(default=0.50, ge=0.0, le=10.0)


class ClaudeScoring(BaseModel):
    """Configuration de l'étage 4 (scoring + pitch via Claude)."""

    model_config = ConfigDict(extra="forbid")

    # Modèle Claude à utiliser. Défaut Haiku 4.5 (~0.005 €/lead).
    # Sonnet 4.6 (~0.02 €/lead) à activer pour qualité supérieure.
    modele: Literal["claude-haiku-4-5", "claude-sonnet-4-6"] = "claude-haiku-4-5"

    # Seuil au-delà duquel un lead est marqué `top_lead=True`.
    seuil_top_lead: int = Field(default=70, ge=0, le=100)

    # Inclure (ou non) la génération du pitch_propose.
    # Si False, on économise ~30% de tokens de sortie.
    inclure_pitch: bool = True

    # Contexte client à injecter dans le prompt (description offre + ICP).
    # None → CONTEXTE_CLIENT_DEFAUT (RénoBoost).
    contexte_client: str | None = None

    # Plafond max de tokens de sortie par lead.
    max_tokens_sortie: int = Field(default=400, ge=50, le=4096)


class CampaignConfig(BaseModel):
    """Représente le contenu d'un fichier `config/<client>.yaml`."""

    model_config = ConfigDict(extra="forbid")

    run: RunInfo
    stages: StagesFlags
    secteurs: list[SecteurCible] = Field(min_length=1)
    zone: Zone
    filtres: Filtres = Filtres()
    filtres_entreprise: FiltresEntreprise = Field(default_factory=FiltresEntreprise)
    enrichissement_l3_5: EnrichissementL35 = Field(default_factory=EnrichissementL35)
    claude_scoring: ClaudeScoring = Field(default_factory=ClaudeScoring)
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
# ÉTAGE 3.5 — Enrichissement contacts vérifiés (Dropcontact)
# ════════════════════════════════════════════════════════════════


class LeadStage35(LeadStage3):
    """LeadStage3 + données enrichies via API Dropcontact (étage optionnel).

    L3.5 ne supprime jamais un lead : tous les champs ci-dessous sont
    optionnels. Si le lead n'a pas été envoyé à Dropcontact (filtré ou
    étage désactivé) ou si l'API n'a pas trouvé d'info, les champs
    restent à `None` / `[]` et le lead poursuit le pipeline normalement.
    """

    # Email vérifié par Dropcontact (qualification = correct/incorrect/risky)
    email_dropcontact: str | None = None
    qualification_email_dropcontact: str | None = None  # ex: "correct", "risky"

    # Téléphone direct (souvent ligne fixe entreprise, parfois mobile dirigeant)
    telephone_direct_dropcontact: str | None = None

    # Profil LinkedIn dirigeant
    linkedin_dirigeant_dropcontact: str | None = None

    # Profil LinkedIn entreprise
    linkedin_entreprise_dropcontact: str | None = None

    # Identité dirigeant normalisée par Dropcontact
    civilite_dirigeant_dropcontact: str | None = None  # M / Mme
    prenom_dirigeant_dropcontact: str | None = None
    nom_dirigeant_dropcontact: str | None = None

    # Métadonnées
    enrichi_dropcontact: bool = False  # True si lead envoyé à l'API (succès ou pas)
    enrichissement_erreur: str | None = None  # raison textuelle si KO
    cout_enrichissement_eur: float = 0.0


# ════════════════════════════════════════════════════════════════
# ÉTAGE 4 — Scoring d'intérêt + pitch proposé (Claude)
# ════════════════════════════════════════════════════════════════


class LeadStage4(LeadStage35):
    """LeadStage3 + scoring qualitatif Claude.

    `score_interet`     : 0-100 (perception de l'intérêt commercial)
    `raison_score`      : 1 phrase de justification (en français)
    `pitch_propose`     : 2-3 lignes d'accroche (français), `None` si `inclure_pitch=False`
                          ou si la génération a échoué.
    `top_lead`          : True si `score_interet >= seuil_top_lead`.
    `scoring_modele`    : modèle utilisé (`claude-haiku-4-5` / `claude-sonnet-4-6`).
    `scoring_erreur`    : raison textuelle si scoring impossible (sinon None).
                          Le lead est alors préservé sans `top_lead` (= False).
    """

    score_interet: int | None = None
    raison_score: str | None = None
    pitch_propose: str | None = None
    top_lead: bool = False
    scoring_modele: str | None = None
    scoring_erreur: str | None = None


# ════════════════════════════════════════════════════════════════
# VEILLE — Lead issu d'une source de veille externe (AAA Data, etc.)
# ════════════════════════════════════════════════════════════════


class LeadVeille(LeadStage4):
    """LeadStage4 + colonnes spécifiques veille immatriculations VE.

    Pose le contexte commercial : ce lead vient d'une immatriculation
    récente d'un véhicule électrique en flotte entreprise — signal fort
    de démarche transition énergétique.

    `deja_eu_ve` : flag (pas d'exclusion) — True si ce SIREN a déjà été
                   observé en VE auparavant. False = première acquisition.
    """

    # Source de veille (`aaa_data`, `bonus_eco`, etc.)
    source_veille: str | None = None
    date_run_veille: str | None = None  # YYYY-MM-DD du fichier source

    # Données VE issues du fichier AAA
    date_immatriculation_ve: str | None = None  # YYYY-MM-DD
    marque_ve: str | None = None
    modele_ve: str | None = None
    energie_ve: str | None = None  # EL / HE / HH / EH / H2
    type_vehicule_ve: str | None = None  # VP / VU / PL...

    # Flag historique (n'EXCLUT pas le lead — informationnel)
    deja_eu_ve: bool = False
    premiere_date_ve: str | None = None  # plus ancienne immat VE connue pour ce SIREN


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
