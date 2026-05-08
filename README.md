# RénoBoost Leads

Outil de prospection B2B paramétrable. Pipeline en 4 étages.

**Architecture en 4 étages indépendants** :
1. **Étage 1 — Découverte** : établissements via Google Places API (~0.05€/lead)
2. **Étage 2 — Entreprises** : SIREN / NAF / dirigeants via API data.gouv.fr (**gratuit**)
3. **Étage 3 — Contacts** : emails via scraping mentions légales + patterns (**gratuit**)
4. **Étage 4 — Prospection** : scoring + hooks via Claude (à venir, ~0.02€/lead)

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

---

## 📁 Sortie

Chaque run produit dans `data/output/<YYYY-MM-DD>_<HHMM>_<nom_run>/` :

```
├─ etage1_decouverte.csv         (20 colonnes — Places)
├─ etage2_entreprises.csv        (+ 17 colonnes data.gouv.fr)
├─ etage3_contacts.csv           (+ 8 colonnes contacts)
├─ backups/                      (versions horodatées de chaque CSV)
├─ session.log                   (logs JSON multi-niveaux)
├─ stats_run.json                (métriques run + coûts)
├─ cache.sqlite                  (cache SIREN + pages scrapées)
└─ registre_rgpd.md              (conformité RGPD)
```

---

## 💰 Coûts

| Étage | API | Coût/lead | Pour 200 leads |
|---|---|---|---|
| 1 | Google Places | 0.05 € | ~10 € |
| 2 | data.gouv.fr | **gratuit** | **0 €** |
| 3 | scraping web | **gratuit** | **0 €** |
| 4 | Claude Sonnet (à venir) | 0.02 € | 4 € |
| **Total prévu V1 complet** | | **0.07 €** | **~14 €** |

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
