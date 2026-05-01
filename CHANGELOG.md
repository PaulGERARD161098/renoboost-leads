# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/) — versionning [SemVer](https://semver.org/).

## [0.2.1] — 2026-05-01 — Hardening + documentation

### Added
- **`OPERATIONS.md`** : standards opérationnels (pré-checks, post-checks, procédure de récupération, checklist livraison client, engagement qualité)
- **README** : section "Performances réelles observées" (chiffres run BdR du 1er mai), section "Principes" (précision > volume)
- **Référentiel chaînes étendu** : 189 enseignes (vs 40 v0.2.0). Ajout NH Hotels, Marriott brands, Choice Hotels, Hyatt brands, Wyndham brands, Aparthotels (Adagio, Citadines, Staycity), résidences services seniors (Domitys, Senioriales), distribution étendue, restauration

### Changed
- README : promesses alignées sur réalité observée (51,5% SIREN au lieu de 70-85% théorique)
- Algo détection chaînes : tri par longueur de keyword décroissante (matche d'abord les plus spécifiques)

### Known issues (à corriger en prochaine session)
- 🐛 Race condition OneDrive vs écriture incrémentale CSV → fix prévu : atomic write
- 🐛 `_trouver_dossier_existant()` ne détecte pas le dossier dans certains cas → contournement via `--from-csv`
- 🐛 Cas dossier sans CSV : message d'erreur peu clair en amont
- 🐛 Stat "pas de SIREN trouvé" inclut les chaînes flaguées (compte trompeur)

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
  - Détection chaînes (~40 enseignes) → flag `flag_chaine` + note manuelle
  - 17 nouvelles colonnes
- **Étage 3 — Contacts (gratuit, Stratégie 3)**
  - Scraping mentions légales / pages contact (HTTP simple + BeautifulSoup)
  - User-Agent honnête, robots.txt respecté, rate limit 1 req/s par domaine
  - Génération patterns nominatifs (sur dirigeant L2, sauf chaînes)
  - Génération patterns fonctionnels génériques
  - 8 nouvelles colonnes
- **Mécanismes de redondance**
  - Cache SQLite étendu
  - Sauvegarde incrémentale tous les 20 leads
  - Backups horodatés
  - Mode `resume --session-id`
- **CLI étendue** : `--stages 2`, `--stages 3`, `--stages 1,2,3`, `--from-csv`, `resume`
- **Tests** : 38 nouveaux tests (62 au total)


## [0.1.0] — 2026-05-01 — Livraison L1

### Added
- **Étage 1 — Découverte Google Places**
- Setup projet (Pydantic, settings, logger JSON, budget guard, rate limiter, cache SQLite)
- CLI : `check-connections`, `estimate`, `run --stages 1`
- Documentation : README, COSTS_AND_LIMITS, RGPD_COMPLIANCE
- Tests : 24 tests
- CI : GitHub Actions

### Validated en production
- 200 leads Hérault, 0,93 €, 84% tel, 80% sites
