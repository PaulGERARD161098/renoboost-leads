# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/) — versionning [SemVer](https://semver.org/).

---

## [0.3.0] — 2026-05-04 — Phase A complete (audit dette technique solde)

### Fixed
- **Bug B2** : `_trouver_dossier_existant()` matchait `endswith(client_name)` en strict, ce qui echouait sur :
  - variations de casse (ex: `BdR` vs `..._bdr`)
  - accents differents (ex: `Hérault` vs `..._Herault`)
  - espaces vs underscores (ex: `Mon Client` vs `..._Mon_Client`)
  - Fix : nouvelle fonction `_normalize_for_match()` (lowercase + strip accents + espaces->underscores), suffix `_{normalized}` pour eviter les faux positifs sur noms courts.
- **Bug B3** : message d'erreur peu clair quand le CSV etait introuvable (`lire_stage1_csv`).
  - Fix : distinction entre dossier parent inexistant (session inconnue) vs dossier existant mais CSV absent (avec liste des fichiers presents et suggestion d'action).

### Added
- **CI** : Python 3.13 ajoute a la matrice de test (3.10, 3.11, 3.12, 3.13) pour parite avec l'env de dev local.
- **Tests Bug B2** : `tests/test_trouver_dossier_existant.py` avec 8 tests (TDD strict, 2 commits separes RED + GREEN).
- **Tests Bug B3** : `tests/test_lire_stage1_csv.py` avec 3 tests (TDD strict, 2 commits separes RED + GREEN).

### Validated
- `pytest` : 79/79 tests verts (68 anciens + 11 nouveaux : 3 pour B3 + 8 pour B2)
- `ruff check` : All checks passed!
- `ruff format --check` : tous les fichiers formates
- `pre-commit run --all-files` : tous les hooks passent
- Encodage UTF-8 propre verifie sur tous les fichiers modifies (`exporter.py`, `cli.py`)

### Phase A : OFFICIELLEMENT TERMINEE
Audit dette technique soldee. Les 4 bugs identifies en debut de session 1 (B1-B4) sont desormais tous resolus :
- **B1** (race condition OneDrive) : resolu structurellement par deplacement du repo (v0.2.3)
- **B2** (`_trouver_dossier_existant` matching strict) : fixe en TDD (v0.3.0)
- **B3** (message d'erreur peu clair sur CSV manquant) : fixe en TDD (v0.3.0)
- **B4** (stat SIREN trompeuse) : fixe en TDD (v0.2.3)

### Next : Phase B
Validation ROI commercial des 400 leads existants (Herault + BdR) avant tout investissement L4.
La question fondamentale : *"Est-ce que les leads convertissent en RDV signes ?"*

---

## [0.2.3] — 2026-05-03 — Bug B4 fix + tooling renforce

### Fixed
- **Bug B4** : `stats_l2()` siren_pct et dirigeant_pct incluaient les chaines flaguees dans le denominateur, faussant les KPIs L2.
  - Avant : `siren_pct = nb_siren / n_total` (FAUX si chaines presentes)
  - Apres : `siren_pct = nb_siren / (n_total - nb_chaines)` (correct, zero-safe)
  - Impact : sur le run BdR (200 leads, 10% chaines), le vrai siren_pct passe de 51,5% affiche a ~57,2% reel.
  - Idem pour `dirigeant_pct` et le log `Pas de SIREN trouve` dans `enrichir()`.
- **Bug B1** (race condition OneDrive vs CSV) : resolu structurellement par deplacement du repo de OneDrive vers `C:\dev\renoboost-leads`. La sync OneDrive ne peut plus interferer avec les ecritures CSV incrementales.

### Added
- **Tooling de qualite** :
  - `.pre-commit-config.yaml` avec ruff (lint + format), hygiene checks (trailing whitespace, EOF, YAML/TOML/JSON validation, large files), et **gitleaks** pour la detection de secrets.
  - `.gitattributes` pour normaliser les line endings (LF pour Python/YAML/MD, CRLF pour scripts Windows).
  - Hooks installes via `pre-commit install`, executes automatiquement a chaque commit.
- **Tests Bug B4** : `tests/test_stats_l2.py` avec 6 tests (TDD strict, 2 commits separes RED + GREEN).

### Changed
- **Format global** : `ruff-format` applique sur les 18 fichiers Python du projet (cosmetique uniquement, aucune logique modifiee).
- **Encodage** : tous les fichiers Python critiques verifies en UTF-8 propre (pas de mojibake).

### Validated
- `pytest` : 68/68 tests verts (62 anciens + 6 nouveaux pour B4)
- `ruff check` : All checks passed!
- `ruff format --check` : 34 files already formatted
- `pre-commit run --all-files` : tous les hooks passent
- `gitleaks` : aucun secret detecte dans l'historique Git

### Security
- **Incident cle Google API** (detecte en debut de session) : ancienne cle `AIzaSyAi...Uo2M` revoquee definitivement, nouvelle cle creee avec restriction API (Places New uniquement). Le fichier `.env` qui contenait la cle etait deja gitignore - aucune fuite reelle dans l'historique Git (verifie via gitleaks).
- **Pre-commit hook gitleaks** desormais actif pour bloquer toute future tentative de commit d'un secret.

### Known issues (a corriger en prochaine session)
- `_trouver_dossier_existant()` ne detecte pas le dossier dans certains cas (Bug B2, contournement via `--from-csv`)
- Cas dossier sans CSV : message d'erreur peu clair (Bug B3)

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
