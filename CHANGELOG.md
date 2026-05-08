# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/) — versionning [SemVer](https://semver.org/).

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
