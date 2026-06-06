"""Models Pydantic — structures de données du projet.

Chaque étage enrichit progressivement le `Lead` avec ses propres champs.
Les modèles suivent une logique d'extension : LeadStage2 hérite/contient LeadStage1, etc.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    type: Literal["ville", "departement", "region", "france", "point"]
    # `codes` est requis pour les zones administratives (ville/departement/...).
    # En mode `point` (ciblage d'une zone d'activité par coordonnées), il est
    # optionnel : la zone est définie par latitude/longitude/rayon.
    codes: list[str] = Field(default_factory=list)
    rayon_par_point_km: float = Field(default=10.0, gt=0, le=50)
    pas_grille_km: float = Field(default=15.0, gt=0, le=100)
    # Mode `point` uniquement : centre du cercle de recherche (parc d'activités,
    # adresse de zone). Le rayon réutilise `rayon_par_point_km`.
    # Deux façons de définir le centre :
    #  - latitude + longitude (coordonnées directes), OU
    #  - adresse en clair (ex « Allée de l'Ecopark, Wambrechies ») géocodée via
    #    la Base Adresse Nationale au lancement de l'étage 0.
    # Si les deux sont fournis, les coordonnées priment (pas d'appel BAN).
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    adresse: str | None = None

    @model_validator(mode="after")
    def _verifier_coherence(self) -> Zone:
        if self.type == "point":
            a_coords = self.latitude is not None and self.longitude is not None
            a_adresse = bool(self.adresse and self.adresse.strip())
            if not a_coords and not a_adresse:
                raise ValueError(
                    "zone type='point' exige soit latitude+longitude, "
                    "soit une adresse à géocoder."
                )
        elif not self.codes:
            raise ValueError(
                f"zone type='{self.type}' exige au moins un code dans `codes`."
            )
        return self


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

    # Chiffre d'affaires (€). Source : API gouv (bloc `finances`, comptes publiés).
    ca_min: int | None = Field(default=None, ge=0)
    ca_max: int | None = Field(default=None, ge=0)
    # CA inconnu (comptes non publiés, fréquent en PME) : par défaut on n'évince
    # PAS (cohérent avec rejeter_effectif_inconnu) — on s'appuie sur effectif/catégorie.
    rejeter_ca_inconnu: bool = False

    # Catégorie entreprise INSEE : ex ["PME","ETI"]. Vide = pas de filtre.
    # Catégorie inconnue → jamais évincée (même logique que le CA).
    categorie_entreprise_inclus: list[str] = Field(default_factory=list)

    # Sites
    multi_sites_only: bool = False


class Volume(BaseModel):
    cible: int = Field(gt=0, le=10_000)
    max_par_secteur: int | None = Field(default=None, ge=1)
    # Pagination Text Search : nombre de pages récupérées par recherche
    # (point × secteur). 1 = comportement historique (≤ 20 leads/cellule).
    # L'API Places plafonne le Text Search à 3 pages (~60 résultats). Chaque
    # page supplémentaire = 1 appel facturé (cf. budget guard). Sans effet sur
    # les types natifs (Nearby Search, non paginable).
    max_pages: int = Field(default=1, ge=1, le=3)


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

    # Inclure (ou non) la génération du contenu commercial (pitch + email
    # objet/corps prêt à envoyer). Si False, on économise ~50% de tokens de sortie
    # (score + raison seulement).
    inclure_pitch: bool = True

    # Contexte client à injecter dans le prompt (description offre + ICP).
    # None → CONTEXTE_CLIENT_DEFAUT (RénoBoost).
    contexte_client: str | None = None

    # Plafond max de tokens de sortie par lead. Défaut 800 pour loger l'email
    # complet (objet + corps) en plus du score/raison/pitch.
    max_tokens_sortie: int = Field(default=800, ge=50, le=4096)

    # Par défaut, L4 ne score que les leads qualifiés (hors_filtre_entreprise=False) :
    # inutile de dépenser des tokens pour des leads déjà écartés par les filtres.
    # Passer à True pour scorer aussi les hors-filtre (diagnostic / calibration).
    scorer_hors_filtre: bool = False


class ScrapingL3(BaseModel):
    """Configuration de l'étage 3 (scraping de contacts).

    `signaux_ve` rend pilotables par YAML les marqueurs « flotte / véhicule
    électrique » détectés à coût nul sur les pages déjà téléchargées, puis
    remontés au scoring L4. Forme : `{libellé affiché: motif regex}`, le motif
    étant appliqué sur le texte normalisé (minuscule, sans accents). Utiliser
    des frontières de mot `\\b` pour les acronymes afin d'éviter les faux
    positifs (ex. `\\baper\\b`).

    None → jeu par défaut `MOTS_CLES_VE` (verticales ombrières / IRVE).
    Vide (`{}`) → désactive complètement la détection de signaux.
    """

    model_config = ConfigDict(extra="forbid")

    signaux_ve: dict[str, str] | None = None

    # Nombre de leads scrapés en parallèle (étage 3). 1 = séquentiel (défaut sûr,
    # comportement historique). >1 accélère le gros volume : le scraping est
    # majoritairement de l'attente réseau, et chaque lead vise un domaine distinct.
    # La politesse par hôte (rate-limit) reste respectée (réservation de créneau
    # thread-safe côté scraper).
    parallelisme: int = Field(default=1, ge=1, le=32)

    @field_validator("signaux_ve")
    @classmethod
    def _compilable(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        if v is None:
            return v
        for label, motif in v.items():
            try:
                re.compile(motif)
            except re.error as e:
                raise ValueError(
                    f"signaux_ve['{label}'] : motif regex invalide ({e})"
                ) from e
        return v


class Emetteur(BaseModel):
    """Identité de l'émetteur au nom de qui les mails sont chassés/signés.

    L'outil prospecte POUR un client (l'utilisateur de RénoBoost-Leads) :
    les cold mails générés en L4 doivent être signés au nom de CE client
    (entreprise + coordonnées en pied), pas au nom de RénoBoost.

    `nom_entreprise` est requis ; le reste est optionnel. Quand le bloc
    `emetteur` est absent du YAML, le comportement historique est conservé
    (Claude devine l'émetteur dans le texte libre `contexte_client`).
    """

    model_config = ConfigDict(extra="forbid")

    nom_entreprise: str = Field(min_length=1, max_length=120)
    telephone: str | None = None
    email: str | None = None  # sert aussi de from_email d'envoi (cold mail)
    site_web: str | None = None
    signataire: str | None = None  # nom de la personne qui signe
    fonction: str | None = None  # ex "Gérant", "Responsable commercial"


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
    scraping_l3: ScrapingL3 = Field(default_factory=ScrapingL3)
    claude_scoring: ClaudeScoring = Field(default_factory=ClaudeScoring)
    # Émetteur au nom duquel les mails sont signés/envoyés. None = comportement
    # historique (signature devinée par Claude depuis `contexte_client`).
    emetteur: Emetteur | None = None
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

    # Données financières (API gouv, présentes si comptes publiés)
    chiffre_affaires: int | None = None  # CA dernière année dispo (€)
    resultat_net: int | None = None  # résultat net même année (€)
    annee_finances: str | None = None  # ex "2024"
    categorie_entreprise: str | None = None  # "PME" / "ETI" / "GE" (INSEE)

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

    # Signaux "flotte / véhicule électrique" détectés au scraping L3 (libellés
    # lisibles, ex. ["IRVE", "borne de recharge"]). Indicateur d'achat remonté
    # au scoring L4. Vide si rien détecté ou site non scrapé.
    signaux_ve: list[str] = []


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
    email_objet: str | None = None  # objet de l'email prêt à envoyer
    email_corps: str | None = None  # corps complet (formule + accroche + CTA + signature)
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
# SOCIETEINFO — enrichissement firmographique alternatif / complément L2
# ════════════════════════════════════════════════════════════════


class LeadSocieteinfo(LeadStage2):
    """LeadStage2 + données enrichies via l'API Societeinfo (étage optionnel).

    Societeinfo s'appuie sur les registres officiels FR (INSEE / BODACC / INPI)
    et fournit un meilleur taux de match SIREN + firmographie que le L2 gratuit
    (data.gouv). On l'utilise soit en **alternative** au L2 gratuit, soit en
    **complément ciblé** sur les leads dont le match SIREN reste incertain.

    Flag-not-drop : tous les champs sont optionnels. Si le lead n'a pas été
    envoyé à l'API (filtré / étage désactivé) ou si l'API n'a rien trouvé, les
    champs restent à `None` / `[]` et le lead poursuit le pipeline normalement.
    """

    societeinfo_siren: str | None = None
    societeinfo_naf: str | None = None
    societeinfo_libelle_naf: str | None = None
    societeinfo_effectif: str | None = None  # tranche ou effectif exact selon le plan
    societeinfo_chiffre_affaires: int | None = None
    societeinfo_dirigeant: str | None = None
    societeinfo_email: str | None = None  # email principal (pattern vérifié côté SI)
    societeinfo_emails: list[str] = []  # emails additionnels
    societeinfo_telephone: str | None = None
    societeinfo_site_web: str | None = None
    societeinfo_linkedin: str | None = None

    # Métadonnées
    enrichi_societeinfo: bool = False  # True si lead envoyé à l'API (succès ou pas)
    societeinfo_erreur: str | None = None  # raison textuelle si KO
    cout_societeinfo_eur: float = 0.0


# ════════════════════════════════════════════════════════════════
# PARKINGS APER — lead issu d'un parc de stationnement soumis à la loi APER
# ════════════════════════════════════════════════════════════════


class LeadAper(LeadStage4):
    """LeadStage4 + colonnes spécifiques « ombrière obligatoire loi APER ».

    Pose le contexte commercial : ce lead exploite un parc de stationnement
    extérieur > 1 500 m² → soumis à l'obligation de solarisation (art. 40 loi
    APER, décret n°2024-1023). C'est un prospect *contraint* et *daté* pour
    l'installation d'ombrières photovoltaïques + bornes de recharge.
    """

    # Source (`aper_osm`, `aper_ign`, `aper_manuel`, ...)
    source_aper: str | None = None
    date_run_aper: str | None = None  # YYYY-MM-DD du run

    # Données parking
    identifiant_parking: str | None = None  # id source (OSM way id, etc.)
    surface_parking_m2: float | None = None
    nb_places_estime: int | None = None

    # Calculé à partir de la surface (calendrier réglementaire)
    echeance_aper: str | None = None  # "2026-07-01" ou "2028-07-01"
    priorite_aper: str | None = None  # "haute" (>10 000 m²) / "standard"
    surface_ombrable_m2: float | None = None  # 50 % de la surface (obligation)

    # Flag historique (n'EXCLUT pas le lead — informationnel)
    deja_vu_parking: bool = False


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
    # Email de l'émetteur (cf. CampaignConfig.emetteur). Persisté ici pour que
    # le staging cold-mail puisse résoudre le from_email « auto depuis la session ».
    emetteur_email: str | None = None
