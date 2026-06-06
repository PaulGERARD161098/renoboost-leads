# Worker M3 — exécution des runs

Process long-running qui transforme les **runs** créés dans le CRM (statut
`demande`) en **leads** prospectables. Conçu pour tourner sur **Railway**
(worker, pas de port HTTP exposé).

## Boucle

1. Poll `runs` où `status = 'demande'` (les plus anciens d'abord).
2. **Claim atomique** : passage `demande → en_cours` filtré sur le statut, donc
   un seul worker attrape chaque run même si plusieurs tournent.
3. Exécution d'un `Pipeline` qui émet la progression (`etape_courante`,
   `progress`, `counts`) → l'UI se met à jour en temps réel (Supabase Realtime).
4. Insertion des leads (statut initial `a_valider`).
5. Finalisation : `termine` (progress 100) ou `echoue` (`erreur` renseignée).

## Observabilité (heartbeat)

À chaque poll, le worker écrit un **battement de cœur** dans la table singleton
`worker_heartbeat` (`last_seen_at`, `mode`, `version`, `pending_runs`,
`last_error`). L'UI (pages **Accueil** et **Recherche**) en déduit si le process
tourne : au-delà de 60 s sans battement, il est signalé **silencieux**, et si des
recherches sont en attente, **à l'arrêt** (rouge). La `version` (SHA court du
build) permet de confirmer depuis l'app qu'un redéploiement a bien atterri. Le
heartbeat rapporte aussi la **présence** (jamais la valeur) des clés API du mode
real (`google_places`, `anthropic`, `pappers`, `dropcontact`) → le panneau
« Clés API » de l'UI sait, sans accès Railway, ce qui est prêt pour la vraie
génération. Le heartbeat est best-effort : un échec d'écriture n'interrompt
jamais la boucle. Un **thread dédié** réécrit le heartbeat toutes les
`WORKER_POLL_INTERVAL_S` secondes pour garder `last_seen_at` frais **même
pendant un run long** (sinon la boucle principale, bloquée dans le traitement,
laisserait la pastille paraître « silencieuse »).

## Récupération des runs orphelins (reaper)

Si le worker meurt ou est redéployé **en plein run**, ce run reste figé en
`en_cours` et n'est jamais repris (on ne ramasse que les `demande`). À chaque
poll, le worker remet en file (`en_cours` → `demande`) tout run sans progrès
depuis plus de `WORKER_STALE_RUN_TIMEOUT_S` (15 min par défaut), de sorte qu'il
soit retraité automatiquement. Côté UI, un bouton **« Relancer le traitement »**
permet aussi de le faire à la demande sur un run bloqué ou échoué.

## Modes (`WORKER_MODE`)

- `demo` (défaut) — génère des leads plausibles **sans API externe**. Permet de
  valider toute la chaîne UI → run → leads immédiatement.
- `real` — exécute le **vrai moteur L1→L4** (`renoboost_leads`) via l'orchestrateur
  partagé avec la CLI, puis écrit des leads réels dans Supabase. Le ciblage vient
  de la **verticale fichier** (`verticales/<slug>/verticale.yaml`, source de
  vérité) ; zone/volume/budget viennent du run. Échoue clairement au démarrage si
  une clé L1/L4 manque (cf. ci-dessous).

## Variables d'environnement

| Variable | Requis | Défaut | Rôle |
|---|---|---|---|
| `SUPABASE_URL` | ✅ | — | URL du projet Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | — | Clé **service_role** (contourne RLS) |
| `WORKER_MODE` | — | `demo` | `demo` \| `real` |
| `WORKER_POLL_INTERVAL_S` | — | `5` | Pause entre deux polls à vide |
| `MAX_LEADS_PER_RUN` | — | `500` | Plafond de leads par run |
| `MAX_BUDGET_EUR_PER_RUN` | — | `50` | Plafond budget par run (BudgetGuard) |
| `WORKER_REQUEST_TIMEOUT_S` | — | `30` | Timeout des appels HTTP |
| `WORKER_STALE_RUN_TIMEOUT_S` | — | `900` | Délai sans progrès au-delà duquel un run `en_cours` est jugé orphelin et remis en file (reaper) |
| `WORKER_VERSION` | — | `RAILWAY_GIT_COMMIT_SHA` | Version affichée dans le heartbeat (SHA court). Sur Railway, déduit automatiquement du commit déployé. |
| `LOG_LEVEL` | — | `INFO` | Niveau de log |

⚠️ Utiliser la clé **service_role**, pas la clé `anon` : le worker écrit dans
`leads`/`runs` côté serveur.

### Clés API du mode `real`

Le moteur lit ses clés via `get_settings()` (mêmes variables que la CLI) :

| Variable | Requis (real) | Étage | Rôle |
|---|---|---|---|
| `GOOGLE_PLACES_API_KEY` | ✅ | L1 | Découverte d'établissements (Google Places) |
| `ANTHROPIC_API_KEY` | ✅ | L4 | Scoring + rédaction des e-mails (Claude) |
| `CLAUDE_MODEL` | — | L4 | Modèle Claude (sinon Haiku 4.5 par défaut) |
| `DROPCONTACT_API_KEY` | — | L3.5 | Enrichissement contacts (L3.5 sauté si absente) |
| `PAPPERS_API_KEY` | — | L2 | Fallback firmographique (sinon data.gouv seul) |
| `SOCIETEINFO_API_KEY` | — | L2/L3.7 | Registres officiels (optionnel) |

En mode `real`, si `GOOGLE_PLACES_API_KEY` **ou** `ANTHROPIC_API_KEY` est absente,
le worker marque le run `echoue` avec un message actionnable et ne consomme aucun
crédit. L2 (data.gouv) est gratuit ; L3.5 n'est exécuté que si une clé Dropcontact
est présente. Le `BudgetGuard` coupe le run dès `MAX_BUDGET_EUR_PER_RUN` atteint.

## Lancer en local

```bash
pip install -r worker/requirements.txt
export SUPABASE_URL=https://xxxx.supabase.co
export SUPABASE_SERVICE_ROLE_KEY=eyJ...
python -m worker
```

## Déploiement Railway

Le `Procfile` (racine) déclare `worker: python -m worker`. Sur Railway :
définir les variables ci-dessus, puis déployer — le service tourne en continu
et se relance tout seul après un crash.

## Tests

```bash
pytest tests/test_worker.py -v
```

Les tests utilisent un faux client Supabase en mémoire : aucun réseau requis.
