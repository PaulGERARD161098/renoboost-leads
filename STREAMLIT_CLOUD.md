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

## 3. Configurer les secrets

App settings → **Secrets** → coller le contenu de
`.streamlit/secrets.toml.example` en remplaçant les valeurs :

```toml
GOOGLE_PLACES_API_KEY = "AIza..."
ANTHROPIC_API_KEY = "sk-ant-..."
DROPCONTACT_API_KEY = ""           # vide = L3.5 OFF
MAX_BUDGET_EUR_PER_RUN = 30
# ...
```

Le bridge `_bridge_streamlit_secrets_to_env()` (en haut de `app.py`) recopie
chaque secret vers `os.environ` au démarrage, ce qui fait que `Settings`
les voit comme s'ils venaient d'un `.env`. **Aucune modification de code**
n'est nécessaire pour passer du local au cloud.

## 4. Limites Streamlit Cloud

- **Stockage éphémère** : le filesystem est wipe à chaque redéploiement.
  Les CSV de sessions / sqlite cache **ne sont pas persistés**.
  Pour de la prod, brancher S3 / GCS plus tard (out of scope ici).
- **Pas de cron** : le workflow `veille_quotidienne.yml` reste sur
  GitHub Actions. Streamlit Cloud sert juste l'UI.
- **CPU/RAM partagés** : les runs L1-L4 lourds (>500 leads, scraping massif)
  doivent rester en CLI locale. L'UI Cloud sert à l'exploration / déclenchement
  ponctuel.
- **Upload max** : 50 Mo (configurable dans `.streamlit/config.toml`).
  Largement suffisant pour un CSV AAA Data quotidien (~quelques Mo).

## 5. Test local du bridge secrets

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Remplir les vraies valeurs
streamlit run app.py
```

Si `.streamlit/secrets.toml` existe en local, il est prioritaire sur `.env`
(comportement Streamlit). Sinon, `.env` reste utilisé. **Ne jamais committer
`.streamlit/secrets.toml`** (déjà dans `.gitignore`).

## 6. Mise à jour

Tout `git push` sur la branche déployée déclenche un re-déploiement automatique.
Pour forcer un redémarrage sans push : App → **Reboot app**.
