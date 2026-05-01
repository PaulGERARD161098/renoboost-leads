# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/) — versionning [SemVer](https://semver.org/).

## [Non publié]

### V1 — CLI

#### L0 — Setup projet (à faire)
- [x] Structure du repo
- [x] Configuration GitHub (.gitignore, README, LICENSE)
- [x] Dépendances pyproject.toml
- [x] Templates de config (.env.example, YAML schema)
- [x] Documentation (README, RGPD, COSTS)

#### L1 — Étage 1 Découverte (à faire)
- [ ] Settings Pydantic
- [ ] Models Pydantic (Lead)
- [ ] Client Google Places API (New)
- [ ] Maillage géographique
- [ ] Extracteur Étage 1
- [ ] Budget guard
- [ ] Logger JSON
- [ ] Cache local SQLite
- [ ] CLI minimale (estimate, run --stages 1, check-connections)
- [ ] Export CSV étage 1
- [ ] Tests unitaires geo_grid + budget_guard

#### L2 — Étage 2 Entreprises (à faire)
- [ ] Client Pappers
- [ ] Matcher nom/adresse → SIREN

#### L3 — Étage 3 Contacts (à faire)
- [ ] Client Dropcontact

#### L4 — Étage 4 Prospection (à faire)
- [ ] Client Claude
- [ ] Builder URL LinkedIn
- [ ] Générateur HTML dossiers prospection

#### L5 — Finalisation (à faire)
- [ ] CLI consolidée
- [ ] Tests d'intégration
- [ ] Notebook Colab quickstart
- [ ] Documentation finale
