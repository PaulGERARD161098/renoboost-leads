# Déploiement Streamlit Cloud

Procédure pour mettre l'UI en ligne sur https://share.streamlit.io.

## 1. Pré-requis

- Compte Streamlit Cloud connecté à ton GitHub (`paggerard-boop`)
- Repo `renoboost-leads` accessible (public ou privé avec lecture autorisée)
- Branche cible (généralement `main`)

## 2. Création de l'app

1. Sur https://share.streamlit.io → **New app**
2. Repository : `paggerard-boop/renoboost-leads`
3. Branch : `main`
4. Main file path : `app.py`
5. App URL (optionnel) : `renoboost-leads.streamlit.app`
6. **Deploy**

Streamlit Cloud lit automatiquement :
- `requirements.txt` (racine) → installe les deps Python
- `.streamlit/config.toml` → thème, port, taille upload
- `st.secrets` (App settings → Secrets) → variables d'environnement

## 3. Checklist secrets

App settings → **Secrets**. Copie-colle le bloc TOML ci-dessous en
remplaçant chaque valeur. Les secrets sont injectés dans `os.environ` et
relus par `Settings` exactement comme un `.env`.

```toml
# ─── Étages payants (clés API) ─────────────────────────────────────
GOOGLE_PLACES_API_KEY = "AIza..."        # obligatoire pour L1
ANTHROPIC_API_KEY = "sk-ant-..."         # L4 scoring + agent copilote
DROPCONTACT_API_KEY = "..."              # L3.5 enrichment ; vide = L3.5 dry-run forcé

# ─── Plafonds budget (optionnels, par défaut codés) ────────────────
MAX_BUDGET_EUR_PER_RUN = 30
MAX_LEADS_PER_RUN = 500

# ─── Persistance des sessions (obligatoire en Cloud) ───────────────
# Sans ce bloc, les sessions sont effacées à chaque redéploiement.
STORAGE_BACKEND = "supabase"
SUPABASE_URL = "https://mwaryfscxgrulauwwque.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOi..."  # service_role, PAS anon
SUPABASE_BUCKET = "sessions"

# ─── Auth de l'app (obligatoire en Cloud — l'URL est publique !) ───
APP_PASSWORD = "choisis-un-bon-mdp-ici"

# ─── SMTP (optionnel, active email_report et veille) ───────────────
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "..."
SMTP_PASSWORD = "..."                    # mot de passe d'application Gmail
SMTP_FROM = "..."
SMTP_DESTINATAIRES = "paul@renoboost.fr"
```

### Où trouver les valeurs

| Variable | Où la récupérer |
|---|---|
| `GOOGLE_PLACES_API_KEY` | https://console.cloud.google.com → Identifiants |
| `ANTHROPIC_API_KEY` | https://console.anthropic.com → API Keys |
| `DROPCONTACT_API_KEY` | https://www.dropcontact.com → Mon compte → API |
| `SUPABASE_SERVICE_ROLE_KEY` | Dashboard Supabase projet `RenoboostIA` → **Settings → API → service_role** (PAS `anon`) ⚠️ |
| `APP_PASSWORD` | Toi — choisis un mdp solide, partage-le aux personnes autorisées |

> ⚠️ **`service_role` key** : permet d'accéder aux données en bypassant RLS.
> Ne jamais l'exposer côté client (navigateur), ni la committer dans Git, ni
> la coller dans un Slack public. Si elle fuite, régénère-la dans le dashboard.

## 4. Architecture stockage

Avec `STORAGE_BACKEND=supabase` activé :

```
   ┌────────────────┐                ┌────────────────────┐
   │ Streamlit Cloud│  ◄──tarball──► │ Supabase Storage   │
   │ (UI publique)  │                │ bucket "sessions"  │
   └────────┬───────┘                └────────┬───────────┘
            │                                 │
            │  download/upload                │  liste les sessions
            │  par session_id                 │  via SQL/REST
            │                                 │
            └─────────────────────────────────┘
                      │
                      ▼
         data/output/<session_id>/   ◄── cache local pendant la vie du container
            (éphémère sur Cloud)
```

- **CLI `run`** : à la fin du run, le dossier session entier est `tar.gz` et
  uploadé vers Supabase (idempotent, upsert).
- **UI Streamlit** : à l'ouverture de l'onglet Sessions, liste les ids
  présents dans le bucket (cache 2 min). À la sélection d'une session
  remote-only, auto-download vers `data/output/`.
- **Outil agent `sync_session`** : permet au copilote de pousser/tirer/lister
  les sessions à la demande.

## 5. Limites Streamlit Cloud

- **Stockage éphémère** : OK, contourné par Supabase (cf. section 4).
- **Pas de cron** : le workflow `veille_quotidienne.yml` reste sur
  GitHub Actions. Streamlit Cloud sert juste l'UI.
- **CPU/RAM partagés** : les runs L1-L4 très lourds (>500 leads, scraping
  massif) doivent rester en CLI locale. L'UI Cloud sert à l'exploration,
  déclenchement ponctuel et lecture des sessions.
- **Timeout requête** : ~10 min sur Streamlit Cloud. Un run L1+L2+L3 sur
  ~50 leads passe largement. Au-delà, préférer la CLI locale (qui pushe
  vers Supabase à la fin → visible ensuite depuis l'UI Cloud).
- **Upload max** : 50 Mo (configurable dans `.streamlit/config.toml`).

## 6. Test local du bridge secrets

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Remplir les vraies valeurs (cf. section 3)
streamlit run app.py
```

Si `.streamlit/secrets.toml` existe en local, il est prioritaire sur `.env`
(comportement Streamlit). Sinon, `.env` reste utilisé. **Ne jamais committer
`.streamlit/secrets.toml`** (déjà dans `.gitignore`).

## 7. Validation post-déploiement

Après avoir sauvegardé les secrets et déclenché un redéploiement :

1. Ouvrir l'app → l'écran de login apparaît (si `APP_PASSWORD` est config).
2. Se logger → sidebar montre les 3 clés API en ✓ active + le bucket
   Supabase actif.
3. Onglet **Sessions** → bandeau "💾 N local · ☁ M Supabase".
4. Lancer un run depuis l'onglet **Nouvelle recherche** → à la fin, message
   "☁ Session synchronisée vers Supabase" doit apparaître dans les logs.
5. Forcer un **Reboot app** → revenir sur l'onglet Sessions → la session
   créée doit toujours apparaître (préfixée ☁ remote-only ou déjà locale
   selon timing).

## 8. Mise à jour

Tout `git push` sur la branche déployée déclenche un re-déploiement automatique.
Pour forcer un redémarrage sans push : App → **Reboot app**.
