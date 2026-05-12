# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/) — versionning [SemVer](https://semver.org/).

## [0.4.0] — 2026-05-12 — Sprint 1 : robustesse + filtres entreprise

> Note : version 0.3.0 sautée (tag déjà posé sur un commit antérieur de housekeeping).

### Added — Bloc 3 : filtres entreprise paramétrables (`filtres_entreprise`)
- Nouvelle section YAML avec **6 critères** combinables : `effectif_min/max` (user-friendly),
  `tranche_effectif_inclus` (codes INSEE bruts, prioritaire), `naf_inclus`/`naf_exclus`
  (préfixe libre), `forme_juridique_inclus`/`_exclus` (mix labels SAS/SARL et codes INSEE),
  `multi_sites_only`.
- Stratégie **flag-not-drop** : les leads hors filtres restent dans le pipeline et passent L3
  (scraping/patterns), avec colonnes `hors_filtre_entreprise` + `raison_hors_filtre`.
- Export L3 séparé : `etage3_contacts.csv` (qualifiés) + `etage3_contacts_hors_filtre.csv`
  (flagués) — un seul CSV si aucun filtre actif (backwards-compat).
- Nouvelle colonne L2 `nb_etablissements` (compte exact issu de SIRENE).

### Fixed
- **B5** filtre géographique strict post-Places — Google retournait des leads hors-département
  cible. `lead_dans_zone()` rejette désormais tout CP qui n'appartient pas à `zone.codes`,
  avec gestion explicite Corse 2A/2B via préfixes CP.
- **B6** matching SIREN sur noms commerciaux verbeux — les noms Places enrichis d'une
  description technique (ex "SMI mécanique et outillage de précision...") ne matchaient plus
  la raison sociale courte INSEE. Nouveau `_nettoyer_nom_commercial()` coupe au 1er mot
  descriptif (mécanique, outillage, services, atelier, ...) avant Levenshtein.
- **B7** chargement `.env` dynamique via `dotenv.find_dotenv(usecwd=True)` — le chemin figé
  `PROJECT_ROOT/.env` échouait sur installs non-éditables / CWD différent. Plus besoin
  d'exporter manuellement les vars d'env.

### Changed
- `EnricheurStage2.__init__` accepte un paramètre optionnel `filtres_entreprise`.
- `LeadStage2` enrichi de 3 colonnes (`nb_etablissements`, `hors_filtre_entreprise`,
  `raison_hors_filtre`).
- `_template.yaml` documente la nouvelle section `filtres_entreprise`.
- README enrichi : section "Démo en 30 secondes" + bloc filtres entreprise.

### Tested
- **94 nouveaux tests** sur la branche (B5 +18, B6 +15, B7 +8, B3 +53).
- Total : **173 tests verts**, ruff clean, compatible Python 3.10/3.11/3.12/3.13.


## [0.2.0] — 2026-05-01 — Livraison L2 + L3

### Added
- **Étage 2 — Enrichissement entreprise (gratuit)**
  - Client API `recherche-entreprises.api.gouv.fr` (sans authentification)
  - Algo de matching nom + adresse → SIREN avec scoring (50/30/20/10 pts)
  - Seuil de confiance 60 pts → flag `match_incertain` si insuffisant
  - Détection chaînes (Accor, Carrefour, Ibis, etc.) → flag `flag_chaine` + note manuelle
  - 10 nouvelles colonnes : SIREN, SIRET, NAF, libelle_NAF, forme_juridique, statut_actif, tranche_effectif, libelle_effectif, dirigeant_nom, dirigeant_prenom, dirigeant_qualite, adresse_normalisee, date_creation, score_matching, match_incertain, flag_chaine, note_chaine
- **Étage 3 — Contacts (gratuit, Stratégie 3)**
  - Scraping mentions légales / pages contact (HTTP simple + BeautifulSoup)
  - User-Agent honnête, robots.txt respecté, rate limit 1 req/s par domaine
  - Génération patterns nominatifs (sur dirigeant L2, sauf chaînes)
  - Génération patterns fonctionnels génériques (`direction@`, `contact@`, etc.)
  - 8 nouvelles colonnes : emails_verifies, emails_candidats, domaine_extrait, page_source_emails, nb_emails_verifies, nb_emails_candidats, source_globale, contient_dirigeant_pattern
- **Mécanismes de redondance**
  - Cache SQLite étendu (SIREN trouvés + pages scrapées) → pas de re-paiement
  - Sauvegarde incrémentale tous les 20 leads
  - Backups horodatés dans `data/output/<session>/backups/`
  - Mode `resume --session-id` pour reprendre un run interrompu
- **CLI étendue**
  - `--stages 2`, `--stages 3`, `--stages 1,2,3`
  - `--from-csv` pour reprendre L2/L3 depuis un CSV existant
  - `resume` (commande dédiée)
- **Tests** : 18 nouveaux tests (matcher SIREN + pattern generator)

### Changed
- Pyproject : nouvelles deps `beautifulsoup4`, `lxml`
- Models : `LeadStage2` et `LeadStage3` (héritage progressif)
- Exporter : 3 fonctions d'export distinctes + lecture CSV pour reprise
- Registre RGPD étendu (sources L2 + L3 documentées)

### Tested
- Tests unitaires : matcher SIREN, scoring, détection chaînes, génération patterns, extraction HTML
- Compatible Python 3.10+ (testé 3.12 et 3.14)


## [0.1.0] — 2026-05-01 — Livraison L1

### Added
- **Étage 1 — Découverte Google Places**
  - Client Places API (New) avec field masks optimisés
  - Maillage géographique par grille (référentiel 96 départements + DOM)
  - Filtrage qualité (statut, note, nb avis, présence tel/site)
  - Dédup par place_id + option dédup chaînes
  - 20 colonnes par lead
- **Setup projet**
  - Structure modulaire (Pydantic, validation stricte)
  - Logger JSON multi-niveaux
  - Budget guard hardcodé (stop auto si dépassement €)
  - Rate limiter token bucket
  - Cache SQLite pour reprise sur erreur
- **CLI** : `check-connections`, `estimate`, `run --stages 1`
- **Documentation** : README, COSTS_AND_LIMITS, RGPD_COMPLIANCE
- **Tests** : 24 tests (geo grid, budget guard, mapper)
- **CI** : GitHub Actions
