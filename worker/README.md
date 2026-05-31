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

## Modes (`WORKER_MODE`)

- `demo` (défaut) — génère des leads plausibles **sans API externe**. Permet de
  valider toute la chaîne UI → run → leads immédiatement.
- `real` — point d'extension vers les étages réels (`renoboost_leads.stage0..4`).
  Non branché tant que les clés API ne sont pas fournies ; lève une erreur claire.

## Variables d'environnement

| Variable | Requis | Défaut | Rôle |
|---|---|---|---|
| `SUPABASE_URL` | ✅ | — | URL du projet Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | — | Clé **service_role** (contourne RLS) |
| `WORKER_MODE` | — | `demo` | `demo` \| `real` |
| `WORKER_POLL_INTERVAL_S` | — | `5` | Pause entre deux polls à vide |
| `MAX_LEADS_PER_RUN` | — | `500` | Plafond de leads par run |
| `WORKER_REQUEST_TIMEOUT_S` | — | `30` | Timeout des appels HTTP |
| `LOG_LEVEL` | — | `INFO` | Niveau de log |

⚠️ Utiliser la clé **service_role**, pas la clé `anon` : le worker écrit dans
`leads`/`runs` côté serveur.

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
