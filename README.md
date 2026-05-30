# RénoBoost Leads

Outil de prospection B2B paramétrable. Pipeline en 4 étages.

**Architecture en 4 étages indépendants** :
1. **Étage 1 — Découverte** : établissements via Google Places API (~0.05€/lead)
2. **Étage 2 — Entreprises** : SIREN / NAF / dirigeants via API data.gouv.fr (**gratuit**)
3. **Étage 3 — Contacts** : emails via scraping mentions légales + patterns (**gratuit**)
4. **Étage 4 — Prospection** : scoring d'intérêt + pitch via Claude (Haiku ~0.005€/lead, Sonnet ~0.02€/lead)

---

## ⚡ Démo en 30 secondes

```bash
# Aperçu sans aucune clé API ni appel réseau
python -m renoboost_leads.cli estimate --config config/client_rossini.yaml

# Test des APIs configurées (lit .env)
python -m renoboost_leads.cli check-connections

# Run complet 10 leads industriels Nord 59 — coûte < 1 €
python -m renoboost_leads.cli run --config config/client_rossini.yaml --stages 1,2,3
```

Sortie dans `data/output/<YYYY-MM-DD>_<HHMM>_rossini-test-nord/` (CSV + logs + cache + registre RGPD).

---

## 🚀 Installation

```bash
# 1. Cloner le repo
git clone https://github.com/<TON_USER>/renoboost-leads.git
cd renoboost-leads

# 2. Créer un venv et installer
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 3. Configurer les clés API
cp .env.example .env
# → ouvrir .env et coller GOOGLE_PLACES_API_KEY (les autres clés sont optionnelles
#   pour L2 et L3 qui sont gratuits)

# 4. Vérifier les connexions
python -m renoboost_leads.cli check-connections
```

---

## 🤖 Copilote — agent IA de pilotage (Phase A)

L'agent Claude pilote la prospection en langage naturel. Il a 7 outils
(lister/lire sessions, lancer pipeline, diagnostiquer qualité, lire/proposer
config, prioriser leads, alerter humain) et un budget €/jour persistant
(défaut 5 €/jour, cap dur).

```bash
# Cycle one-shot
python -m renoboost_leads.cli agent run "liste les sessions récentes"
python -m renoboost_leads.cli agent run "diagnostique la session 20260518-..."

# REPL interactif
python -m renoboost_leads.cli agent chat

# État budget + journal
python -m renoboost_leads.cli agent budget
python -m renoboost_leads.cli agent journal -n 10
```

Disponible aussi dans Streamlit (onglet **🤖 Copilote**). Configurable
via `config/agent.yaml` (modèle, cap budget, niveau autonomie).

**Phase A** : pas d'envoi cold mail, pas d'écriture de config sans validation
humaine. **Phase B** : intégration Instantly pour cold mailing N2 (drafte
+ validation manuelle avant envoi).

### Phase B — Cold mailing Instantly avec staging N2

L'agent drafte les emails, **toi tu valides**, puis seulement les items
'valide' sont poussés dans Instantly. Aucun envoi sans clic humain.

```bash
# 1. L'agent drafte (via chat ou run)
python -m renoboost_leads.cli agent run \
    "stage 10 cold mails pour la session <sid> en secteur compta"

# 2. Toi tu valides item par item (CLI ou Streamlit onglet Copilote)
python -m renoboost_leads.cli cold-mail list
python -m renoboost_leads.cli cold-mail show <staging_id>
python -m renoboost_leads.cli cold-mail validate \
    --staging-id <stg> --lead-id <siren>
python -m renoboost_leads.cli cold-mail refuse \
    --staging-id <stg> --lead-id <siren>

# 3. Envoi des validés vers Instantly
python -m renoboost_leads.cli cold-mail send --staging-id <stg>

# 4. Suivi
python -m renoboost_leads.cli cold-mail metrics --campaign-id <id>
```

Configuration : `INSTANTLY_API_KEY` dans `.env`, `INSTANTLY_DRY_RUN=false`
quand prêt. Tant que pas configuré, tout est simulé (dry-run automatique).

Secteurs disponibles : `compta`, `avocats`, `immo`, `com`, `be` (5 templates
3-step sous `templates/sequences/`).

## 🎯 Utilisation

### Estimer le coût

```bash
python -m renoboost_leads.cli estimate --config config/client_ombrieres.yaml
```

### Étage 1 seul (découverte Google Places)

```bash
python -m renoboost_leads.cli run --config config/client_ombrieres.yaml --stages 1
```

### Étage 2 sur un CSV L1 existant (gratuit)

```bash
python -m renoboost_leads.cli run --config config/client_ombrieres.yaml --stages 2
```

### Étage 3 sur un CSV L2 existant (gratuit)

```bash
python -m renoboost_leads.cli run --config config/client_ombrieres.yaml --stages 3
```

### Pipeline complet 1+2+3

```bash
python -m renoboost_leads.cli run --config config/client_ombrieres.yaml --stages 1,2,3
```

### Étage 4 — Scoring Claude sur un CSV L3 existant

```bash
# Requiert ANTHROPIC_API_KEY dans .env
python -m renoboost_leads.cli run --config config/client_ombrieres.yaml --stages 4
```

Le scoring produit pour chaque lead : `score_interet` (0-100), `raison_score`,
`pitch_propose` (2-3 lignes) et `top_lead` (booléen au-delà du seuil).

Cache automatique : un re-run avec mêmes paramètres (`modele`, `contexte_client`,
`inclure_pitch`) est gratuit.

#### Valider le flux L4 sans clé Anthropic (dry-run)

```bash
python -m renoboost_leads.cli run \
  --config config/client_rossini.yaml \
  --stages 4 --dry-run
```

Les scores et pitchs sont simulés (préfixés `[DRY-RUN]`), aucun appel réseau,
le CSV `etage4_prospection.csv` est écrit normalement. Pratique pour tester
l'UI Streamlit et le câblage CLI avant d'engager du budget.

### Veille immatriculations VE flotte (AAA Data)

Module dédié pour ingérer le flux quotidien AAA Data des immatriculations VE
entreprise et le brancher sur le pipeline RénoBoost. Voir [VEILLE.md](./VEILLE.md).

```bash
# Dry-run (pas de clé Anthropic nécessaire)
python -m renoboost_leads.cli veille run --fichier exemple_aaa.csv --dry-run

# Mode normal
python -m renoboost_leads.cli veille run --fichier exemple_aaa.csv --budget 2.0
```

### Parkings loi APER (prospects ombrières contraints)

Module dédié pour ingérer un inventaire de parcs de stationnement, isoler ceux
soumis à l'obligation de solarisation (loi APER, parkings > 1 500 m²) et les
passer dans le pipeline RénoBoost. Voir [PARKINGS_APER.md](./PARKINGS_APER.md).

```bash
# Dry-run (pas de clé Anthropic nécessaire)
python -m renoboost_leads.cli aper run \
  --fichier tests/fixtures_parkings/echantillon_parkings_demo.csv --dry-run

# Mode normal
python -m renoboost_leads.cli aper run --fichier inventaire_parkings.csv --budget 2.0
```

### Enrichissement Societeinfo (firmographie FR)

Commande autonome pour enrichir un CSV de leads (match SIREN, CA, dirigeant,
contacts) via l'API Societeinfo — ciblage intelligent sur les leads dont le
match gratuit a échoué. Voir [SOCIETEINFO.md](./SOCIETEINFO.md).

```bash
# Dry-run (données simulées si SOCIETEINFO_API_KEY absente)
python -m renoboost_leads.cli enrich-societeinfo \
  --from-csv data/output/<session>/etage2_entreprises.csv --dry-run
```

### Étage 3.7 — Complétion (repêchage + enrichissement)

Étage **générique** intégré au pipeline `run`, qui à la fois **enrichit**
l'existant (NAF, effectif, CA, dirigeant…) **et repêche** ce que les étages
classiques n'ont pas trouvé (SIREN, dirigeant, email) via une source externe
(provider Societeinfo, swappable). Remplissage *fill-if-empty* + provenance
tracée. Deux livrables par run : `etage3_7_completion.csv` + l'annexe
`completion.md`. Voir [COMPLETION.md](./COMPLETION.md).

```bash
# Opt-in dans un run complet (dry-run sans clé) :
python -m renoboost_leads.cli run --config config/client_rossini.yaml \
  --stages 1,2,3,3.5,3.7,4 --dry-run

# Sur un CSV L3 existant uniquement :
python -m renoboost_leads.cli run --config config/client_rossini.yaml \
  --stages 3.7 --from-csv data/output/<session>/etage3_contacts.csv
```

### Interface Streamlit (visualisation + déclenchement L4)

```bash
pip install -e ".[ui]"
streamlit run app.py
```

L'app lit les sessions dans `data/output/`, affiche les leads L3 / L4,
et permet de lancer L4 depuis l'UI (lecture clé `ANTHROPIC_API_KEY`
depuis `st.secrets` ou `.env`).

### Reprendre une session interrompue

```bash
python -m renoboost_leads.cli resume \
  --session-id 2026-05-01_1833_ombrieres-bouches-du-rhone \
  --stages 2,3 \
  --config config/client_ombrieres.yaml
```

### Repartir d'un CSV L1 spécifique

```bash
python -m renoboost_leads.cli run \
  --config config/client_ombrieres.yaml \
  --stages 2,3 \
  --from-csv data/output/<session>/etage1_decouverte.csv
```

### Conformité RGPD — effacement et purge

```bash
# Aperçu (recommandé d'abord)
python -m renoboost_leads.cli forget --email contact@exemple.fr --dry-run

# Effacement réel d'un lead — par email, SIREN ou place_id
python -m renoboost_leads.cli forget --email contact@exemple.fr --motif "demande client"
python -m renoboost_leads.cli forget --siren 123456789
python -m renoboost_leads.cli forget --place-id ChIJxxxxx

# Purge des sessions > 3 ans (défaut, dry-run par défaut)
python -m renoboost_leads.cli cleanup
python -m renoboost_leads.cli cleanup --older-than-days 90 --mode archive
python -m renoboost_leads.cli cleanup --mode delete
```

Voir [RGPD_COMPLIANCE.md](./RGPD_COMPLIANCE.md) pour le détail.

---

## 📁 Sortie

Chaque run produit dans `data/output/<YYYY-MM-DD>_<HHMM>_<nom_run>/` :

```
├─ etage1_decouverte.csv               (20 colonnes — Places)
├─ etage2_entreprises.csv              (+ 20 colonnes data.gouv.fr)
├─ etage3_contacts.csv                 (qualifiés + 8 colonnes contacts)
├─ etage3_contacts_hors_filtre.csv     (leads hors `filtres_entreprise` — si actifs)
├─ backups/                            (versions horodatées de chaque CSV)
├─ session.log                         (logs JSON multi-niveaux)
├─ stats_run.json                      (métriques run + coûts)
├─ cache.sqlite                        (cache SIREN + pages scrapées)
└─ registre_rgpd.md                    (conformité RGPD)
```

---

## 🎯 Filtres entreprise (post-L2)

Section optionnelle du YAML pour cibler par effectif, NAF, forme juridique, multi-sites. Les leads hors-cible sont **flagués** (pas rejetés) et exportés dans un CSV séparé pour ne pas mélanger.

```yaml
filtres_entreprise:
  effectif_min: 50                    # ou tranche_effectif_inclus: ["21","22"]
  naf_inclus: ["25", "28", "29"]      # préfixe libre — "25" matche "25.62A"
  naf_exclus: ["56"]                  # exclure restauration
  forme_juridique_inclus: ["SAS","SARL","SA"]
  forme_juridique_exclus: ["EI","EIRL"]
  multi_sites_only: false             # exige nb_etablissements > 1
```

---

## 💰 Coûts

| Étage | API | Coût/lead | Pour 200 leads |
|---|---|---|---|
| 1 | Google Places | 0.05 € | ~10 € |
| 2 | data.gouv.fr | **gratuit** | **0 €** |
| 3 | scraping web | **gratuit** | **0 €** |
| 4 | Claude Haiku 4.5 (défaut) | 0.005 € | 1 € |
| 4 | Claude Sonnet 4.6 (option) | 0.02 € | 4 € |
| **Pipeline complet (Haiku)** | | **~0.055 €** | **~11 €** |

Voir [COSTS_AND_LIMITS.md](./COSTS_AND_LIMITS.md) pour le détail.

---

## ⚖️ Conformité RGPD

Voir [RGPD_COMPLIANCE.md](./RGPD_COMPLIANCE.md). Base légale : intérêt légitime (B2B).

---

## 📊 Limites honnêtes (gratuit vs payant)

| Métrique | L2 gratuit | Pappers payant |
|---|---|---|
| Taux match SIREN | 70-85 % | 92-95 % |
| Effectif | Tranche INSEE | Idem |
| CA exact | ❌ | ✅ |
| Dirigeants | Principal | Tous + historique |

| Métrique | L3 gratuit | Dropcontact payant |
|---|---|---|
| Taux email trouvé | 50-65 % | 80-90 % |
| Email vérifié | ❌ (à valider via NeverBounce) | ✅ |
| Email décideur | 15-25 % | 40 % |

→ **Workflow conseillé pour envoi** : exporter CSV L3 → vérifier via NeverBounce ou ZeroBounce (~5-10€/1000 vérifs) → importer dans Lemlist/Smartlead.

⚠️ **Ne JAMAIS** envoyer en cold email sans vérification batch préalable (bounce > 15 % = domaine grillé).

---

## 📝 Licence

MIT — voir [LICENSE](./LICENSE).
