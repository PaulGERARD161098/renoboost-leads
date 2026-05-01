# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/) — versionning [SemVer](https://semver.org/).

---

## [0.2.2] — 2026-05-01 — Lint cleanup

### Fixed
- **F601** : doublon de clé `"première classe"` dans le référentiel chaînes (la 2ème occurrence écrasait silencieusement la 1ère)
- **F401** : 4 imports inutilisés retirés (`COUT_NEARBY_SEARCH_EUR`, `datetime`, `Path`, `Any`)
- **E741** : 8 variables `l` ambiguës (PEP8) renommées en `lead`
- **E501** : 3 lignes > 100 caractères découpées proprement
- **S110/S112** : 2 try/except silencieux passent maintenant `logger.debug()` (au lieu de `pass`/`continue` muet)

### Validated
- `ruff check .` : All checks passed
- `pytest` : 62/62 tests verts
- Aucune régression fonctionnelle

---

## [0.2.1] — 2026-05-01 — Hardening + documentation

### Added
- **`OPERATIONS.md`** : standards opérationnels (pré-checks, post-checks, procédure de récupération, checklist livraison client, engagement qualité)
- **README** : section "Performances réelles observées" (chiffres run BdR du 1er mai), section "Principes" (précision > volume)
- **Référentiel chaînes étendu** : 189 enseignes (vs 40 v0.2.0). Ajout NH Hotels, Marriott brands, Choice Hotels, Hyatt brands, Wyndham brands, Aparthotels (Adagio, Citadines, Staycity), résidences services seniors (Domitys, Senioriales), distribution étendue, restauration

### Changed
- README : promesses alignées sur réalité observée (51,5% SIREN au lieu de 70-85% théorique)
- Algo détection chaînes : tri par longueur de keyword décroissante (matche d'abord les plus spécifiques)

### Known issues (à corriger en prochaine session)
- Race condition OneDrive vs écriture incrémentale CSV — fix prévu : atomic write
- `_trouver_dossier_existant()` ne détecte pas le dossier dans certains cas — contournement via `--from-csv`
- Cas dossier sans CSV : message d'erreur peu clair en amont
- Stat "pas de SIREN trouvé" inclut les chaînes flaguées (compte trompeur)

### Validated en production (run BdR 200 leads, 1er mai 2026)
- L1 : 200 leads, téléphone 84%, site web 80%, ~1 €
- L2 : SIREN 51,5%, dirigeants 30,5%, chaînes 10%, 0 €
- L3 : email scrapé 27,5%, au moins 1 email 75%, patterns nominatifs 26,5%, 0 €

---

## [0.2.0] — 2026-05-01 — Livraison L2 + L3

### Added
- **Étage 2 — Enrichissement entreprise (gratuit)**
  - Client API `recherche-entreprises.api.gouv.fr` (sans authentification)
  - Algo de matching nom + adresse → SIREN avec scoring (50/30/20/10 pts)
  - Seuil de confiance 60 pts → flag `match_incertain` si insuffisant
  - Détection chaînes (~40 enseignes initialement) → flag `flag_chaine` + note manuelle
  - 17 nouvelles colonnes : SIREN, SIRET, NAF, libelle_NAF, forme_juridique, statut_actif, tranche_effectif, libelle_effectif, dirigeant_nom, dirigeant_prenom, dirigeant_qualite, adresse_normalisee, date_creation, score_matching, match_incertain, flag_chaine, note_chaine
- **Étage 3 — Contacts (gratuit, Stratégie 3)**
  - Scraping mentions légales / pages contact (HTTP simple + BeautifulSoup)
  - User-Agent honnête, robots.txt respecté, rate limit 1 req/s par domaine
  - Génération patterns nominatifs (sur dirigeant L2, sauf chaînes)
  - Génération patterns fonctionnels génériques (`direction@`, `contact@`, etc.)
  - 8 nouvelles colonnes : emails_verifies, emails_candidats, domaine_extrait, page_source_emails, nb_emails_verifies, nb_emails_candidats, source_globale, contient_dirigeant_pattern
- **Mécanismes de redondance**
  - Cache SQLite étendu (SIREN trouvés + pages scrapées)
  - Sauvegarde incrémentale tous les 20 leads
  - Backups horodatés dans `data/output/<session>/backups/`
  - Mode `resume --session-id` pour reprendre un run interrompu
- **CLI étendue**
  - `--stages 2`, `--stages 3`, `--stages 1,2,3`
  - `--from-csv` pour reprendre L2/L3 depuis un CSV existant
  - `resume` (commande dédiée)
- **Tests** : 38 nouveaux tests (62 au total : matcher SIREN + pattern generator)

### Changed
- Pyproject : nouvelles dépendances `beautifulsoup4`, `lxml`
- Models : `LeadStage2` et `LeadStage3` (héritage progressif)
- Exporter : 3 fonctions d'export distinctes + lecture CSV pour reprise
- Registre RGPD étendu (sources L2 + L3 documentées)

---

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

### Validated en production
- 200 leads Hérault, 0,93 €, 84% téléphone, 80% sites
