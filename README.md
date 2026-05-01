# RénoBoost Leads

Outil de prospection B2B paramétrable. Extraction Google Places + enrichissement Pappers/Dropcontact + scoring/hooks Claude.

**Architecture en 4 étages indépendants** :
1. **Étage 1 — Découverte** : établissements Google Places
2. **Étage 2 — Entreprises** : SIREN / NAF / dirigeants via Pappers
3. **Étage 3 — Contacts** : emails vérifiés via Dropcontact
4. **Étage 4 — Prospection** : scoring + hooks personnalisés via Claude

---

## 🚀 Installation

```bash
# 1. Cloner le repo
git clone https://github.com/<TON_USER>/renoboost-leads.git
cd renoboost-leads

# 2. Créer un venv et installer
python3 -m venv .venv
source .venv/bin/activate  # sous Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 3. Configurer les clés API
cp .env.example .env
# → ouvrir .env et coller ta clé GOOGLE_PLACES_API_KEY (autres optionnelles)

# 4. Vérifier les connexions
python -m renoboost_leads.cli check-connections
```

---

## 🎯 Utilisation rapide

```bash
# Estimer le coût d'un run avant de le lancer
python -m renoboost_leads.cli estimate --config config/client_ombrieres.yaml

# Lancer uniquement l'étage 1 (découverte Places)
python -m renoboost_leads.cli run --config config/client_ombrieres.yaml --stages 1

# Lancer le pipeline complet (1+2+3+4)
python -m renoboost_leads.cli run --config config/client_ombrieres.yaml

# Reprendre une session interrompue
python -m renoboost_leads.cli resume --session-id <ID>
```

---

## 📁 Sortie

Chaque run produit dans `data/output/<YYYY-MM-DD_<nom_run>>/` :

```
├─ etage1_decouverte.csv       (12 colonnes — Places)
├─ etage2_entreprises.csv      (+ 10 colonnes Pappers)
├─ etage3_contacts.csv         (+ 8 colonnes Dropcontact)
├─ etage4_prospection.csv      (+ 5 colonnes scoring + hooks)
├─ dossiers_prospection/       (1 fichier HTML par lead)
├─ session.log                 (log JSON multi-niveaux)
├─ stats_run.json              (métriques run)
└─ registre_rgpd.md            (conformité RGPD)
```

---

## 💰 Coûts estimés

| Étage | API | Coût/lead | Pour 200 leads |
|---|---|---|---|
| 1 | Google Places | 0.06 € | 12 € |
| 2 | Pappers | 0.12 € | 24 € |
| 3 | Dropcontact | 0.20 € | 40 € |
| 4 | Claude Sonnet | 0.02 € | 4 € |
| **Total** | | **0.40 €** | **80 €** |

Voir [COSTS_AND_LIMITS.md](./COSTS_AND_LIMITS.md) pour le détail.

---

## ⚖️ Conformité RGPD

Voir [RGPD_COMPLIANCE.md](./RGPD_COMPLIANCE.md).

---

## 📝 Licence

MIT — voir [LICENSE](./LICENSE).
