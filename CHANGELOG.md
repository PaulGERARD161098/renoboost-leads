# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/) — versionning [SemVer](https://semver.org/).

## [Unreleased] — Ciblage Rossini : SIRENE-first + témoin hors-filtre

### Added — moteur

- **Découverte SIRENE-first opt-in par verticale** (`cibles.decouverte_sirene_first`,
  schéma `verticale/schema.py`). À `true`, le worker découvre par `naf_inclus`
  **nativement à la source gratuite** (recherche-entreprises.api.gouv.fr, étage 0)
  et n'utilise plus Places que pour l'enrichissement par nom — au lieu d'un Text
  Search large payé puis filtré a posteriori. Défaut `false` (Places-first inchangé).
- **Témoin de ciblage** dans `RunStats` (`leads_decouverts`, `nb_hors_filtre`,
  `taux_hors_filtre`), calculé en fin de pipeline et persisté dans `run_stats.json`.
  Surfacé en fin de run CLI (`🎯 Ciblage : N/M hors-filtre (X %)`). Permet de
  confirmer la baisse du hors-filtre sans run témoin à l'aveugle.

### Changed

- **Verticale Rossini** passée en SIRENE-first (`decouverte_sirene_first: true`) :
  vise à éliminer le ~72 % de hors-filtre observé en Places-first (requêtes larges
  « usine » / « siège social » payées puis jetées). Le run témoin réel reste une
  étape OPS sur le worker (clés Google Places / Anthropic).

## [1.2.0] — Mail piloté par les potentiels + LinkedIn dans la fiche

### Added

- **Brouillon mail piloté par l'analyse v2** (`web/lib/outreach.ts`) : le cold
  mail / la relance mettent en avant le **meilleur potentiel** (solaire /
  ombrières / bornes), intègrent le **contexte bornes de la zone** et relient
  l'angle à l'offre du client. Repli inchangé sur l'estimation v1.
- **LinkedIn dans la fiche prospect** : `leads.contact_linkedin` +
  `leads.entreprise_linkedin` (migration `0034`), propagés depuis Dropcontact
  (déjà collectés en L3.5, jusqu'ici jetés au mapping worker). Affichés en liens
  cliquables dans la carte « Décideur ».
- **Enrichissement contact on-demand** : bouton « Enrichir le contact » →
  route `/api/lead/enrich-contact` (Dropcontact, polling borné `maxDuration` 60 s)
  qui remplit email / téléphone / LinkedIn pour un lead, sans écraser le vide.

## [Unreleased] — Lancement V1 : accueil d'Henry + boucle de retours

### Added — accueil « V1 en ligne » d'Henry (joué une seule fois)

- **Confirmation préalable** : à la reconnexion d'Henry, un écran demande
  d'abord *« Est-ce que vous voulez vous connecter à Outil Leads V1 pour la
  première fois ? »*. La cinématique ne démarre qu'après acceptation ; un
  « Pas maintenant » ferme sans marquer l'accueil comme vu (reproposé au login
  suivant).
- **Cinématique de bienvenue** (`web/components/welcome-v1.tsx`,
  `web/lib/welcome-v1.ts`) : « vidéo » scriptée ~20 s (cartes auto-déroulées,
  barre de progression, *skippable*, voix off optionnelle via synthèse
  navigateur). Titre : *« Bienvenue sur LEADS, Henry ! Voilà à quoi a servi ton
  argent ! »*. Résume les fonctionnalités et se clôt sur la chute convenue.
- **Réservée à Henry** (`henry.huvey@renoboostia.fr`) et **jouée une seule
  fois** : horodatée par `profiles.welcomed_v1_at` (migration 0033). Déclenchée
  à son prochain login.

### Added — boucle de retours structurée (drainée par Claude)

- **Pop-up de retours d'Henry** (`web/components/feedback-dock.tsx`) : monté
  dans le layout → **suit Henry sur toutes les pages**. Il consigne ses retours
  en vrac (page courante auto-jointe) ; ils s'empilent dans la table `retours`.
  Henry tape **« fin du retour »** (ou le bouton) pour clore → le pop-up
  disparaît.
- **Magellan capte les idées d'amélioration** (Paul & co) : une note produit
  adressée à l'assistant (« il faudrait… », « amélioration : … ») est rangée
  dans `retours` (source `magellan`) au lieu d'appeler le modèle. Magellan
  confirme et rappelle qu'**aucun changement ne se fait sans la validation de
  Paul**.
- **Acheminement** : la table `retours` (migration 0033, RLS authenticated) est
  drainée par Claude en session (lecture Supabase) → correctifs **proposés en
  PR draft**, jamais appliqués sans validation de Paul (garde-fou CLAUDE.md).
- Server actions `logRetour` / `markWelcomedV1` (`web/lib/actions/feedback.ts`),
  détection d'intention `web/lib/feedback.ts`.

## [0.11.0] — 2026-05-19 — Déploiement en ligne : persistance Supabase + auth

### Added — persistance des sessions sur Supabase Storage

Sans ça, le filesystem éphémère de Streamlit Cloud effaçait toutes les
sessions à chaque redéploiement. La plateforme devient maintenant
**réellement utilisable en ligne** : runs lancés depuis l'app déployée,
sessions visibles depuis n'importe quel poste.

- **Nouveau module `src/renoboost_leads/storage/`** :
  - Protocol `SessionStorage` (`upload_session`, `download_session`,
    `list_remote_sessions`, `delete_remote_session`)
  - Backend `local` (défaut, no-op — `data/output/` reste source de vérité)
  - Backend `supabase` (tarball gzippé par session, bucket privé,
    upsert idempotent, file_size_limit 50 MB)
  - Factory `get_storage()` qui lit `settings.storage_backend`
- **Bucket Supabase `sessions`** créé dans projet `RenoboostIA`.
- **Hook fin de CLI run** : upload auto vers Supabase si
  `STORAGE_BACKEND=supabase`. Échec d'upload non bloquant pour le run.
- **Sécurité** : extract tarball refuse `..` / paths absolus
  (path traversal protection, type CVE-2007-4559). `service_role` key
  utilisée uniquement côté serveur Python.

### Added — Streamlit affiche local + Supabase fusionnés

- Onglet **Sessions** : header bandeau "💾 N local · ☁ M Supabase",
  bouton **🔄 Resync liste** (cache st.cache_data ttl=120s).
- Le selectbox merge les sessions locales et les sessions remote-only
  (préfixées `☁`). **Auto-download** dès qu'une session remote-only est
  sélectionnée.
- Aucun changement d'API pour les sessions purement locales (rétrocompat).

### Added — outil agent `sync_session`

13ᵉ outil agent : `sync_session(session_id, direction="up|down|list")`.
Permet au copilote de pousser/tirer des sessions vers/depuis Supabase,
ou de lister ce qui est dans le bucket. En backend local, c'est un
no-op qui renvoie `skipped=True`.

### Added — auth mot de passe pour l'app Streamlit déployée

- Variable `APP_PASSWORD` : si renseignée, l'app demande le mdp avant
  rendu de l'UI (mode prod). Si vide, l'app est ouverte (mode dev local).
- Comparaison **constant-time** via `hmac.compare_digest` (anti
  timing-attack).
- Bouton **🚪 Déconnexion** dans la sidebar (n'apparaît que si auth actif).
- Stockage du flag dans `st.session_state` — pas de cookie persistant, le
  rechargement onglet/fermeture refait passer par le login.

### Changed — settings

5 nouvelles variables (toutes optionnelles, défaut = comportement actuel) :
- `STORAGE_BACKEND` : `local` (défaut) | `supabase`
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_BUCKET`
- `APP_PASSWORD`

Documentées dans `.env.example`.

### Internal

- Dépendance `supabase>=2.8.0` ajoutée à `requirements.txt` (Streamlit
  Cloud la pulle automatiquement) et `pyproject.toml` (extra `storage`).
- **+22 tests** (16 sur `storage/`, 6 sur `sync_session`). 617 tests
  verts, ruff clean.

### Action requise utilisateur (sinon backend reste `local`)

1. Récupérer la `service_role` key sur le dashboard Supabase du projet
   `RenoboostIA` (Settings → API → `service_role`).
2. La poser dans `.env` local + Secrets Streamlit Cloud avec
   `STORAGE_BACKEND=supabase` + `SUPABASE_URL` + `SUPABASE_BUCKET=sessions`.
3. Choisir un `APP_PASSWORD` et l'ajouter aux Secrets Streamlit Cloud
   pour protéger l'app publique. Voir `STREAMLIT_CLOUD.md`.

## [0.10.0] — 2026-05-19 — Navigation L3.5/L4 via l'agent + UI symétrique

### Added — 2 outils agent ciblés

Le copilote IA peut désormais piloter finement les étages L3.5 et L4 sur
une **session existante**, sans relancer tout le pipeline.

- **`enrich_l3_5_on_session(session_id, dry_run)`** : lance L3.5
  (Dropcontact — email vérifié, tél direct, LinkedIn) sur une session
  ayant déjà L3. Subprocess CLI, extraction de stats post-CSV (%email
  qualifié, %tel direct, %LinkedIn, coût). Préfère cet outil à
  `run_pipeline` quand la session existe.
- **`score_l4_on_session(session_id, dry_run)`** : lance L4 (scoring
  Claude + pitch) sur une session existante. Source automatique : L3.5
  prioritaire, fallback L3. Retourne top_leads, score moyen/médian,
  %pitch.
- Registry agent passe de 10 à **12 outils**.

### Added — bouton "Enrichir L3.5" dans l'onglet Sessions Streamlit

UX symétrique au bouton "Lancer L4" existant : dès qu'une session a L3,
deux boutons côte-à-côte permettent d'ajouter L3.5 puis L4 à la souris.
Checkboxes dry-run par défaut quand la clé API correspondante est
absente. Sidebar affiche désormais l'état de la clé **Dropcontact**.

### Changed — `diagnose_quality` étendu aux 3 étages

- Renvoie désormais `metriques_l3_5` (4 indicateurs Dropcontact :
  %email, %email "correct", %tel, %LinkedIn) au lieu de 2.
- Renvoie `metriques_l4` quand `etage4_prospection.csv` présent
  (top_leads, score moyen/médian, %pitch, %raison).
- Renvoie `etages_presents` : liste des étages effectivement présents
  dans la session.

### Changed — `compare_sessions` étendu aux étages L3.5 et L4

Le diff de qualité couvre désormais L3.5 (%email Dropcontact, %tel
direct) et L4 (delta top_leads, delta score moyen) quand les deux
sessions comparées les ont. Format du retour : `metriques_a.l3 |
.l3_5 | .l4` (auparavant plat). Le verdict textuel reste basé sur L3
pour cohérence avec le pilote Phase 1.

### Fixed — désalignement nom fichier L3.5

`STAGE_FILES["3.5"]` pointait vers `etage3_5_enrichment.csv` (anglais)
alors que le CLI produit `etage3_5_enrichissement.csv` (français).
Conséquence : `diagnose_quality`, `list_sessions`, `prioritize_leads`
ne voyaient jamais L3.5 en prod. Aligné sur le vrai nom produit par le
CLI.

### Changed — prompt système agent à jour

`agent/prompts/system.md` retire la mention obsolète "Phase A : pas
d'outils cold mailing" (Phase B est livrée depuis 0.8.0). Liste les 12
outils par usage, donne des règles rapides de choix entre
`run_pipeline` / `enrich_l3_5_on_session` / `score_l4_on_session`.

### Internal

- Nouveau module `agent/tools/enrich.py` (~280 lignes, subprocess CLI).
- Nouvelles fonctions `_metriques_l4()` et stats Dropcontact étendues
  dans `quality.py`.
- `app.py` : simplification du bouton L4 (in-process → subprocess via
  outil agent), suppression des imports devenus inutilisés
  (`ClaudeClient`, `EnricheurStage4`, `CacheStage4`...).
- **+15 tests** (10 sur `enrich`, 3 sur `quality`/L4, 2 sur `compare`
  L3.5/L4).

## [0.9.1] — 2026-05-19 — Cosmétiques rapport HTML (livrable client)

### Fixed — lisibilité du rapport `generate_report`

Patch cosmétique du rapport HTML livré au client : les codes bruts
INSEE / NAF n'apparaissent plus, les téléphones ne se cassent plus sur
deux lignes, les noms d'entreprises mal saisis dans Google Places et les
formats dirigeants incohérents sont normalisés à l'affichage.

- **Décodage tranches d'effectif INSEE** : les codes "01", "02", "11",
  "12"... sont remplacés par leur libellé humain ("1 ou 2 salariés",
  "3 à 5 salariés", "10 à 19 salariés"...) dans le tableau et la
  distribution. Priorité au `libelle_effectif` fourni par l'API
  recherche-entreprises, fallback sur décodage du code via dict.
- **Libellés NAF** : la distribution sectorielle affiche
  `47.91B — Vente à distance...` plutôt que le code seul.
- **Téléphones nowrap** : classe CSS `td.nowrap` ajoutée pour empêcher
  la coupure `04 91 12` ↵ `34 56` quand la cellule est étroite.
- **Noms d'entreprises "espacés"** : recolle automatiquement les
  séquences de ≥ 3 lettres isolées séparées par des espaces
  ("S H C I LOGISTIQUE" → "SHCI LOGISTIQUE"). Heuristique conservatrice
  (2 tokens isolés → laissés tels quels).
- **Dirigeants** : format propre `Prénom NOM (Qualité)`, avec
  title-case automatique des prénoms tout-majuscules
  ("GAMBATESA" → "Gambatesa"), suppression du doublon quand
  `prenom == nom` ("JAZ (JAZ)" → "JAZ"), et capitalisation de la
  qualité ("GÉRANT" → "Gérant").
- **Nouveau module `agent/tools/_formatters.py`** centralisant les
  helpers `decode_effectif`, `format_naf`, `nettoyer_nom_espaces`,
  `format_dirigeant` (et dict `LIBELLES_TRANCHE_EFFECTIF`).
- Aucune modification du CSV stocké : le nettoyage est strictement à
  l'affichage (traçabilité préservée).
- **+31 tests** (23 helpers + 8 intégration rapport HTML).

## [0.9.0] — 2026-05-18 — Rapport HTML autonome (livrable client)

### Added — outil `generate_report` + bouton Streamlit

Permet de produire un **livrable visuel** pour le client à partir d'une
session de prospection : rapport HTML autonome (CSS inline, aucune
ressource externe) ouvrable dans n'importe quel navigateur. Pour un PDF,
l'utilisateur fait `Ctrl+P → Enregistrer en PDF` côté navigateur (zéro
dépendance lourde côté serveur).

- **Module `agent/tools/report.py`** (8e outil agent) : génère le HTML
  à partir de `etage3_contacts.csv` + `run_stats.json`, calcule les KPI
  qualité, applique le verdict pilote Phase 1, inclut un tableau des
  leads (par défaut top 50, max 200). Écrit dans
  `data/output/<session_id>/rapport.html` par défaut, ou chemin
  personnalisable.
- **Sections du rapport** : header campagne, KPI grid (4 metrics :
  total leads / SIREN / dirigeant / email), verdict GO/NO-GO Phase 2
  avec critères, tableau leads (raison sociale, ville, SIREN,
  dirigeant, email, téléphone, site, effectif), distribution
  effectifs, KPI L3.5 si présent (email vérifié, tél direct), sources
  pipeline, footer.
- **Onglet Sessions Streamlit** : nouveau bouton "📄 Générer le
  rapport HTML" + slider max_leads + bouton "⬇ Télécharger" une fois
  généré. Dispo dès que L3 existe (pas besoin de L4).
- **+9 tests** (couverture session inconnue, L3 absent, HTML complet,
  verdict NO-GO, troncature max_leads, output_path personnalisé,
  inclusion L3.5, registry agent).

Tests : **504 verts** (vs 495). Ruff clean.

## [0.8.0] — 2026-05-18 — Cold mailing Instantly (Phase B N2) + robustesse agent

### Added — Phase B cold mailing avec staging N2 (validation humaine)
Bascule l'agent Copilote d'une posture "analyse + propose" à
"prospection complète bout-en-bout" : 7 → 12 outils, et l'agent peut
maintenant **drafter** des campagnes cold mail que l'utilisateur valide
manuellement avant envoi Instantly. Aucun cold mail ne part sans clic
humain (garde-fou N2).

- **Wrapper Instantly v2** (`instantly/client.py`) : 5 méthodes (create
  campaign, list, add leads, get analytics, pause) avec mode dry-run
  automatique si pas de clé ou si `INSTANTLY_DRY_RUN=true`.
- **Templates séquences** (`templates/sequences/*.md`) : 5 secteurs
  (compta, avocats, immo, com, BE), 3 steps chacun avec délais J+0,
  J+4-5, J+7-8. Front-matter YAML + corps markdown. Variables
  substituables ({{civilite}}, {{prenom}}, {{nom_dirigeant}},
  {{nom_entreprise}}, {{telephone_paul}}, {{lien_calendly}}).
- **Staging workflow** (`instantly/staging.py`) : StagingStore JSON
  persistant sous `data/cold_mail/staging/<id>.json`. 4 états par item :
  en_attente / valide / refuse / envoye.
- **5 nouveaux outils agent** (`agent/tools/cold_mail.py`) :
  `stage_cold_emails`, `list_stagings`, `send_validated`
  (idempotent, envoie UNIQUEMENT les 'valide'), `read_campaign_metrics`,
  `pause_campaign`.
- **CLI** : sous-groupe `cold-mail {list, show, validate, refuse, send,
  metrics}`. Tableau Rich des stagings + previews par couleur d'état.
- **Streamlit** : section "📨 Staging cold mail" ajoutée à l'onglet
  Copilote — selectbox + métriques + expanders par item avec boutons
  Valider/Refuser/Envoyer.

### Added — robustesse agent Phase A (paliers C1-C3)
- **Prompt caching Anthropic** (system + tools ephemeral 5 min) — ~70%
  d'économie input tokens à partir du 2e cycle dans la fenêtre.
  CycleResult expose tokens_cache_creation/read, budget recalcule au
  tarif × 1.25 (write) / × 0.10 (read).
- **Rotation journal** à 200 KB → archive `journal-archive-YYYYMM.md`
  + troncature contexte LLM à 10 KB (~2.5k tokens). Journal reste
  lisible même après 1000+ cycles.
- **Métriques par outil** persistées (`data/agent/metrics.json`) :
  count, duration_total_s, erreurs par outil + CLI `agent metrics`
  (panel + tableau Rich trié par fréquence).
- conftest.py autouse fixture qui isole `data/agent/*` et
  `data/cold_mail/*` vers tmp_path pour éviter pollution en test.

### Settings ajoutées
- `INSTANTLY_API_KEY` (SecretStr optionnel)
- `INSTANTLY_BASE_URL` (défaut https://api.instantly.ai/api/v2)
- `INSTANTLY_DRY_RUN` (défaut True — bascule à False quand abo actif)

### Tested
- **+158 tests** (Phase B + robustesse) : 495 total (vs 344 sur main).
  Ruff clean, Python 3.10-3.12.
- Tous les tests Instantly utilisent mocks HTTP ou dry-run — aucune
  hit API réelle, aucun coût.

### .gitignore
- `data/agent/` et `data/cold_mail/` ajoutés (même politique que
  `data/output/`).

## [0.7.0] — 2026-05-18 — Agent Copilote Phase A

### Added — agent IA autonome de pilotage prospection
Premier socle d'un agent qui prend des instructions en langage naturel
("liste les sessions", "diagnostique la dernière", "priorise les leads")
et appelle les bons outils via Claude tool-use.

- **7 outils exposés au LLM** (`src/renoboost_leads/agent/tools/`) :
  - `list_sessions(limit)` : énumère `data/output/`, plus récentes d'abord,
    détecte les étages disponibles (1, 2, 3, 3_hors_filtre, 3.5, 4).
  - `read_session(session_id, stage, sample_size)` : stats + N premiers leads.
  - `run_pipeline(config_path, stages, dry_run)` : wrap subprocess `cli run`.
  - `diagnose_quality(session_id)` : % SIREN matché, dirigeant, email,
    distribution effectif/NAF, anomalies, **verdict Phase 1 pilote**
    (SIREN>80%, dirigeant>50%, email>40%).
  - `read_config(path)` / `propose_config_edit(path, contenu_cible, motif)` :
    lecture YAML sous `config/` (chroot strict), éditions = diff unifié
    sans écriture (garde-fou Phase A).
  - `prioritize_leads(session_id, top_n)` : scoring chaud/tiède/froid
    auto-sélection L4 > L3.5 > L3 + distribution + médiane.
  - `alert_human(subject, body, urgency)` : email SMTP via Settings
    existant. 3 niveaux (info / attention / urgent).
- **Runner Claude tool-use** (`agent/runner.py`) : boucle complète avec
  budget €/jour persistant (`agent/budget.py`), journal markdown append-only
  (`agent/journal.py`), prompt système (`prompts/system.md`), config YAML
  (`config/agent.yaml`).
- **CLI** : sous-groupe `renoboost-leads agent {run, chat, journal, budget}`.
  - `agent run "instruction"` : one-shot.
  - `agent chat` : REPL.
  - `agent journal -n 10` : lecture journal.
  - `agent budget` : état €/jour.
- **UI Streamlit** : 5e onglet 🤖 Copilote avec métriques budget, zone
  instruction, affichage tours/coût/tokens, journal récent.

### Garde-fous Phase A
- Budget cap €/jour persistant (reset minuit UTC, par défaut 5 €).
- Niveau d'autonomie N2 — pas d'écriture config sans validation user,
  pas d'envoi cold mail (Phase B = Instantly, à venir).
- Chroot `config/` strict pour `read_config` (rejette `..` et chemins
  absolus hors zone).
- Cap `max_outils_par_cycle` pour éviter boucles infinies.
- Toutes les erreurs d'outil sont passées au LLM (pas de raise) pour
  qu'il puisse réagir intelligemment.

### Tested
- **+76 tests** (journal, budget, config, 5 outils, runner mocké).
- Total : **404 tests verts** (vs 328 sur main). Ruff clean, Python 3.10-3.12.
- Runner testé sans hit Anthropic (client mocké, fake responses).

### Notes Phase B
Phase B (à coder ensuite) = intégration **Instantly** pour cold mailing
en mode N2 (drafte campagnes, validation email humain avant envoi).
Décision actée : Instantly retenu vs Lemlist (37 €/mois, automatisation
native plus avancée).

## [Unreleased] — dettes techniques

### Added — smoke test L4 prêt-à-l'emploi (dette #3)
- `scripts/generate_l3_fixture.py` : génère une fixture L3 de 5 leads variés
  (cabinet médical, PME méca, BE énergie, restaurant, hôtel chaîne) à l'endroit
  attendu par `scripts/premier_test_l4.sh`. Gratuit, déterministe, fixture
  validée par `lire_stage3_csv`.
- `scripts/premier_test_l4.sh` : ajout d'une étape `2/5 Fixture L3` qui appelle
  le générateur si le CSV est absent. Le script passe de 4 à 5 étapes, marche
  désormais **du premier coup** sans pré-run L1→L3 (avant : plantait si la
  fixture n'existait pas localement).

### Added — commandes CLI RGPD (dette #2)
- **`cli forget --email/--siren/--place-id [--motif] [--dry-run]`** : automatise
  le droit à l'effacement. Balaie toutes les sessions `data/output/<session>/`,
  efface les lignes matchant dans tous les `etage*.csv` (qualifiés + hors-filtre
  + L3.5 + L4) et leurs `backups/`, purge les caches SQLite (`cache.sqlite`,
  `cache_l3_5.sqlite`, `cache_l4.sqlite`) sur les `place_id` concernés, inscrit
  la demande dans `data/effacements_log.csv` (date ISO 8601, type, valeur,
  sessions touchées, lignes effacées, motif).
- **`cli cleanup --older-than-days N --mode {dry-run,archive,delete}`** :
  purge automatique des sessions plus anciennes que N jours (défaut 3 ans
  CNIL). Mode `dry-run` par défaut pour éviter toute perte accidentelle ;
  `archive` crée un `tar.gz` dans `data/archives/<session>.tar.gz` avant
  suppression ; `delete` supprime directement.
- Nouveau module pur `cli_rgpd.py` (testable sans Click).

### Tested
- 16 nouveaux tests (`test_cli_forget.py` ×9, `test_cli_cleanup.py` ×7) :
  matching email/SIREN/place_id, multi-CSV + backups, purge caches SQLite,
  log RGPD, dry-run, modes archive/delete, validation entrées.
- Total : **344 tests verts** (vs 328). Ruff clean.

### Changed — docs
- `RGPD_COMPLIANCE.md` : sections "Droit à l'effacement" et "Suppression
  automatique" réécrites — la procédure manuelle est remplacée par la
  commande CLI dédiée.

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
