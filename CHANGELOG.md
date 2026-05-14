# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/) — versionning [SemVer](https://semver.org/).

## [0.6.0] — 2026-05-14 — Sprint 3 : L3.5 Dropcontact + export CRM + Streamlit Cloud

### Added — Étage 3.5 : enrichissement contacts vérifiés (Dropcontact)
- Nouveau module `stage3_5_enrichment/` :
  - `client.py` : wrapper Dropcontact (POST batch + polling avec timeout, retry
    tenacity, budget guard, hooks injectables pour tests sans monkeypatch).
  - `cache.py` : SQLite (`cache_l3_5.sqlite`) avec invalidation sur
    `(provider, language, siren, schema_version)`.
  - `enricher.py` : orchestrateur L3 → L3.5 — **filtre intelligent** (ne traite
    que les leads `hors_filtre_entreprise=False` avec dirigeant/site + SIREN),
    découpe en batchs (50 par défaut), erreurs granulaires (api_error,
    budget_exhausted, unexpected) sans perte de lead.
  - `dry_run.py` : client factice qui synthétise email/tel/LinkedIn plausibles
    sans appel réseau (pour `--dry-run` et tests).
- Nouvelle section YAML `enrichissement_l3_5` (provider, language, siren,
  batch_size, polling, cout_par_lead_eur).
- Flag `enable_stage_3_5_enrichment` dans `StagesFlags`.
- 11 nouvelles colonnes L3.5 : `email_dropcontact`,
  `qualification_email_dropcontact`, `telephone_direct_dropcontact`,
  `linkedin_dirigeant_dropcontact`, `linkedin_entreprise_dropcontact`,
  `civilite_dirigeant_dropcontact`, `prenom_dirigeant_dropcontact`,
  `nom_dirigeant_dropcontact`, `enrichi_dropcontact`,
  `enrichissement_erreur`, `cout_enrichissement_eur`.
- CLI : `--stages 3.5` câblé dans `run`, `_executer_stage3_5`,
  `export_stage3_5_csv` / `lire_stage3_5_csv`. L4 lit prioritairement L3.5
  (puis L3) pour ne pas perdre l'enrichissement.

### Added — Export CSV exportable (CRM-ready)
- `COLONNES_EXPORT_CRM` : vue curatée (24 colonnes) — nom, SIREN, NAF,
  effectif, ville, dirigeant, email vérifié, tel direct, LinkedIn, score, pitch.
- `export_csv_crm()` accepte n'importe quelle famille de leads (L3/L3.5/L4).
- Nouvelle commande CLI `export --session-id <id> [--source auto|l4|l3.5|l3]
  [--top-only] [--avec-email-uniquement] [--output <path>]`.
- UI Streamlit (onglet Sessions) : 3 boutons côte-à-côte — CSV L4 complet,
  CSV exportable CRM, Top leads exportables.

### Added — Déploiement Streamlit Cloud
- `requirements.txt` racine (lu par Streamlit Cloud, miroir des deps
  `pyproject.toml` + `streamlit` + install éditable du package).
- `.streamlit/config.toml` : thème vert, headless, upload max 50 Mo.
- `.streamlit/secrets.toml.example` : template à coller dans App settings →
  Secrets (Streamlit Cloud).
- `_bridge_streamlit_secrets_to_env()` dans `app.py` : recopie `st.secrets`
  vers `os.environ` au démarrage pour que `Settings` (pydantic-settings) les
  voie comme un `.env`. Aucune modif de code pour passer local → cloud.
- `STREAMLIT_CLOUD.md` : procédure déploiement + limites (stockage éphémère,
  pas de cron, CPU partagé) + test local du bridge.

### Tests
- 31 nouveaux tests : `test_stage3_5_client.py` (8), `test_stage3_5_enricher.py`
  (17 — filtre, cache, batch, dry-run, erreurs, callback, stats),
  `test_export_csv_crm.py` (6 — round-trip CSV + commande CLI).
- Total : **328 tests verts** (vs 297 sur 0.5.0). Ruff clean.

### Changed
- `LeadStage4` hérite désormais de `LeadStage35` (nouveau) au lieu de
  `LeadStage3`. Backward-compatible : tous les champs L3.5 ont des défauts.
- `lire_stage4_csv` passe par `lire_stage3_5_csv` → les anciens CSV L4 (sans
  colonnes Dropcontact) restent lisibles, les nouveaux hydratent L3.5.

## [0.5.0] — 2026-05-13 — Sprint 2 : L4 (scoring Claude) + UI Streamlit

### Added — Étage 4 : scoring d'intérêt + pitch via Claude
- Nouveau module `stage4_prospection/` avec :
  - `prompt_template.py` : prompt versionné (`PROMPT_VERSION="v1"`) + contexte
    `CONTEXTE_CLIENT_DEFAUT` (RénoBoost), override via `contexte_client` YAML/UI.
  - `client.py` : wrapper SDK Anthropic (retry + budget guard + parsing JSON strict +
    calcul coût € à partir des tokens).
  - `cache.py` : cache SQLite séparé (`cache_l4.sqlite`) avec invalidation auto sur
    changement (`prompt_version`, `modele`, `contexte_client`, `inclure_pitch`).
  - `enricher.py` : orchestrateur L3 → L4 avec sauvegarde incrémentale tous les 20 leads,
    gestion d'erreur granulaire (parse / API / budget) sans perte de lead.
- Nouvelle section YAML `claude_scoring` (modèle, seuil top_lead, inclure_pitch,
  contexte_client custom, max_tokens_sortie).
- 6 nouvelles colonnes L4 : `score_interet` (0-100), `raison_score`, `pitch_propose`,
  `top_lead`, `scoring_modele`, `scoring_erreur`.
- CLI : `--stages 4` câblé dans `run`, fonction `_executer_stage4`,
  `export_stage4_csv` / `lire_stage4_csv` + `lire_stage3_csv` (reprise L4 sur CSV L3).
- Modèle par défaut **Haiku 4.5** (~0.005 €/lead), **Sonnet 4.6** disponible en YAML
  (~0.02 €/lead).

### Added — Interface Streamlit
- `app.py` : visualisation des sessions `data/output/`, affichage L3 / L4 avec
  colonnes triées (score, top_lead, raison, pitch), métriques rapides
  (total / top / score moyen / erreurs), download CSV.
- Bouton **Activer L4** sur les sessions L3 sans L4 : sélection modèle, seuil,
  pitch on/off, contexte custom, plafond budget, progress bar live, écriture
  `etage4_prospection.csv` + cache.
- Lecture clé `ANTHROPIC_API_KEY` : `st.secrets` → `.env` → saisie sidebar
  (non persistée). Nouveau extra `pip install -e ".[ui]"`.

### Changed
- `CampaignConfig` : nouveau champ `claude_scoring: ClaudeScoring` (défaut Haiku).
- `LeadStage4` étend `LeadStage3` (héritage progressif maintenu).
- `check-connections` : statut Claude détaillé (clé présente + modèle par défaut).
- `estimate` : coût L4 calculé en fonction du modèle (Haiku ou Sonnet).
- README + COSTS_AND_LIMITS + OPERATIONS + RGPD : section L4 dédiée
  (incluant statut sous-traitant Anthropic + référence DPA + SCC).

### Tested
- **62 nouveaux tests L4** : prompt rendering, cache + invalidation (modèle / contexte /
  pitch), parsing JSON (pur, fenced codeblock, invalide), bornes 0-100,
  budget guard, calcul coût Haiku vs Sonnet, flux enricher complet (cache hit,
  parse_error, budget_exhausted, callback incrémental), client dry-run
  (déterministe, scores 30-95, cache compatible).
- Nouveau test d'intégration optionnel `tests/test_stage4_integration.py`
  (marker `integration`) qui hit la vraie API si `ANTHROPIC_API_KEY` est
  présente, skip sinon.
- CI étendue à `app.py` (ruff + smoke ast).
- Total : **235 tests verts** (hors intégration), ruff clean.

### Added — Mode dry-run L4
- `ClaudeClientDryRun` (`stage4_prospection/dry_run.py`) : mock du client SDK
  qui retourne des scores déterministes 30-95 dérivés du hash du prompt,
  sans appel réseau ni clé.
- `--dry-run` étendu pour couvrir `--stages 4` : `_executer_stage4` accepte
  un drapeau dry-run et injecte automatiquement le mock. Permet de valider
  le flow complet (CLI + cache + exporter + UI) sans engager de budget.

### Changed
- `EnricheurStage4._enrichir_un_lead` renommé public `enrichir_un_lead`
  (l'app Streamlit n'utilise plus de méthode `_privée`).
- `.env.example` : `CLAUDE_MODEL` aligné sur Haiku 4.5 (cohérent avec le code).
- `RGPD_COMPLIANCE.md` : procédure manuelle d'effacement documentée (les
  commandes `cli forget` / `cli cleanup` mentionnées précédemment ne sont
  pas implémentées — note explicite ajoutée).


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
