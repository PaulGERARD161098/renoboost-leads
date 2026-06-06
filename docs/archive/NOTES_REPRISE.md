# Note de reprise — relancer une recherche (ex. Rossini) + check complet

> Rédigée le 26/05/2026. Objectif : pouvoir rouvrir une session et relancer une
> campagne de prospection sans rien chercher, avec un check propre des prérequis.

---

## 0. Branches — savoir où on est

- **`main`** → moteur pipeline + features récentes (#22 filtre CA, #23 email L4).
  Les critères Rossini y vivent sous forme de config YAML.
- **`claude/prospecting-automation-platform-9mq8j`** → **plateforme verticale**
  (objets Verticale/Campagne + agent conversationnel). Merge prévu dans `main`
  le **1er juin**.
  ⚠️ Cette branche n'a probablement **pas encore** #22/#23 → conflits à prévoir
  au merge (les deux ont touché `stage2`/`stage4`).

Pour l'expérience « agent + verticale » → travailler sur `9mq8j`.
Pour un run simple tout de suite → `main` suffit (config `client_rossini.yaml`).

---

## 1. Où sont les critères Rossini (déjà sauvegardés, rien à re-saisir)

- **Forme legacy (`main`)** : `config/client_rossini.yaml`
  - secteurs : `usine` / `entrepôt logistique` / `siège social`
  - zone : Nord (59), grille 15 km / rayon 12 km
  - filtres : effectif ≥ 20 ; NAF inclus `10, 20, 22-33, 49, 52, 53, 70.10`
  - (#22 permet d'ajouter `ca_min`/`ca_max` + catégorie PME/ETI)
- **Forme verticale (`9mq8j`)** : `verticales/rossini/verticale.yaml`
  - = offre (ombrières bois + bornes IRVE), signaux APER/VE, qualification,
    ton mail, séquence J0/J3/J7. **Plus riche** que le YAML legacy.
  - ⚠️ La **zone n'est pas** dans la verticale → elle vit dans la **campagne**.

---

## 2. Clés API / env — le « beau check » (fichier `.env` à la racine)

**Obligatoire pour un run :**

| Variable | Rôle | Coût |
|---|---|---|
| `GOOGLE_PLACES_API_KEY` | L1 découverte | payant ~0,05 €/lead — sans ça, rien |
| `ANTHROPIC_API_KEY` | L4 scoring + email perso | ~0,005 €/lead (Haiku) |
| `CLAUDE_MODEL` | modèle par défaut | `claude-haiku-4-5` |

**Optionnel :**

| Variable | Rôle | Note |
|---|---|---|
| `DROPCONTACT_API_KEY` | L3.5 emails vérifiés (~0,5 €/lead) | ⚠️ **crédits épuisés (48)** → recharger avant activation |
| `PAPPERS_API_KEY` | CA / santé financière fine | sinon CA gratuit via data.gouv (#22) |
| `INSTANTLY_API_KEY` | cold mailing | `INSTANTLY_DRY_RUN=true` tant que pas prêt |
| `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` + `STORAGE_BACKEND=supabase` | persistance sessions | indispensable si app en ligne (sinon sortie éphémère) |
| `APP_PASSWORD` | mot de passe app Streamlit déployée | |
| `SMTP_*` | veille immatriculations VE par mail | |

**Plafonds de sécurité** (modifiables) :
`MAX_BUDGET_EUR_PER_RUN=30` · `MAX_LEADS_PER_RUN=500` · `MAX_REQUESTS_PER_MINUTE=60`

> L2 (data.gouv/SIREN) et L3 (scraping) sont **gratuits**, aucune clé requise.

---

## 3. Check au démarrage (dans l'ordre)

```bash
git status && git log --oneline -5          # état propre + dernier travail
git branch -a                               # repérer main vs 9mq8j
pip install -e ".[dev]"                      # (re)installer si nouveau conteneur
python -m renoboost_leads.cli check-connections   # teste les clés du .env
python -m pytest -q                          # vert (≈621 sur main / 679 sur 9mq8j)
```

---

## 4. Relancer une recherche Rossini

**A) Estimer le coût AVANT (gratuit, aucun appel réseau)**
```bash
python -m renoboost_leads.cli estimate --config config/client_rossini.yaml
```

**B) Voie legacy (sur `main`)**
```bash
python -m renoboost_leads.cli run --config config/client_rossini.yaml --stages 1,2,3,4
# 1=Places  2=SIREN  3=scraping  4=score+email  (ajouter 3.5 si Dropcontact rechargé)
```

**C) Voie verticale / agent (sur `9mq8j`)**
```bash
python -m renoboost_leads.cli verticales list
python -m renoboost_leads.cli verticales show rossini
python -m renoboost_leads.cli campagnes list
python -m renoboost_leads.cli campagnes run <id_campagne> --dry-run   # preview
python -m renoboost_leads.cli campagnes run <id_campagne>             # réel (humain only)
# ou en conversation : agent chat → "lance une campagne verticale rossini, zone X, budget Y"
```

**D) Récupérer le livrable HTML après un run**
```bash
python scripts/generer_emails_html.py data/output/<session>/etage4_prospection.csv sortie.html
# (scripts/generer_rapport_html.py pour la vue "leads")
```

---

## 5. Garde-fous à ne pas oublier

- Un run = du **temps** (~30 min à 2 h) + de l'**argent** (Google surtout). Pas instantané.
- Sur le web/cloud, `data/output/` est **éphémère** (non commité) → exporter/commiter
  le CSV ou le HTML pour le garder.
- Lancement réel = **action humaine** (l'agent ne fait que composer/preview).
- data.gouv peut renvoyer des **503** sur gros volume → si L2 échoue en masse,
  purger le cache `stage2_search` + supprimer `cache_l4.sqlite` avant de relancer
  `--stages 2,3,4` (sinon la relance lit les résultats vides en cache).
