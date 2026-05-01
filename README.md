# RénoBoost Leads

Outil de prospection B2B paramétrable. Pipeline en 4 étages.

**Architecture en 4 étages indépendants** :
1. **Étage 1 — Découverte** : établissements via Google Places API (~0.005€/lead)
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
  --session-id 2026-05-01_2042_ombrieres-bouches-du-rhone \
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

## ⚖️ Principes de l'outil

> **Précision avant volume.** L'outil ne génère **jamais** de données fausses ou inventées.
> Les champs vides sont préférables aux suppositions. Les promesses sont alignées sur la réalité.

- ✅ Aucun SIREN faux : seuil de confiance 60 pts strict + flag `match_incertain`
- ✅ Aucun dirigeant inventé : champ vide si non trouvé
- ✅ Aucune chaîne traitée comme indépendant : 189 enseignes détectées + flag dédié
- ✅ Tous les emails L3 sont soit **scrapés du site** (publics LCEN) soit **flagués comme patterns à vérifier**

---

## 💰 Coûts (mesurés sur 200 leads BdR — 1er mai 2026)

| Étage | API | Coût/lead | Pour 200 leads |
|---|---|---|---|
| 1 | Google Places | 0.005 € | ~1 € |
| 2 | data.gouv.fr | **gratuit** | **0 €** |
| 3 | scraping web | **gratuit** | **0 €** |
| 4 | Claude Sonnet (à venir) | 0.02 € | ~4 € |
| **Total V1 complet** | | **~0.025 €/lead** | **~5 €** |

Voir [COSTS_AND_LIMITS.md](./COSTS_AND_LIMITS.md) pour le détail.

---

## ⚖️ Conformité RGPD

Voir [RGPD_COMPLIANCE.md](./RGPD_COMPLIANCE.md). Base légale : intérêt légitime (B2B).

---

## 📊 Performances réelles observées (pas théoriques)

> ⚠️ Les chiffres ci-dessous sont issus de runs réels sur 200 leads en
> Bouches-du-Rhône (1er mai 2026), pas de promesses marketing.

### Étage 1 — Découverte
| Métrique | Hérault | Bouches-du-Rhône |
|---|---|---|
| Leads atteints | 200/200 | 200/200 |
| Téléphone trouvé | 84 % | 84 % |
| Site web trouvé | 80 % | 80 % |
| Pertinence (5 random) | 5/5 | 5/5 |
| Coût | 0,93 € | ~1 € |

### Étage 2 — Entreprises (data.gouv.fr)
| Métrique | Run BdR | Limite gratuit |
|---|---|---|
| Match SIREN confiant (≥60 pts) | 42 % | — |
| Match SIREN incertain (<60 pts) | 9 % | — |
| **SIREN total** | **51,5 %** | (Pappers payant : 92-95 %) |
| Dirigeant trouvé | 30,5 % | (Pappers : 60-70 %) |
| Chaînes flaguées | 10 % | — |
| Coût | 0 € | — |

⚠️ **L'API data.gouv.fr couvre incomplètement les indépendants à noms exotiques**
(châteaux, mas, résidences services). Pour les leads sans SIREN, les données L1
(téléphone + site web + adresse) restent exploitables en cold call.

### Étage 3 — Contacts (scraping + patterns)
| Métrique | Run BdR |
|---|---|
| Email scrapé du site (vérifié) | 27,5 % |
| Au moins 1 email (scrapé OU pattern) | 75 % |
| Patterns nominatifs (sur dirigeant L2) | 26,5 % |
| Sans email (pas de site web en L1) | 15 % |
| Chaînes ignorées (volontaire) | 10 % |
| Coût | 0 € |

⚠️ **Les emails `candidats` (patterns) doivent être validés via NeverBounce ou ZeroBounce
avant envoi** (~5-10€ pour 1000 vérifications). Ne JAMAIS envoyer sans vérification :
bounce > 15% = domaine grillé.

---

## 🛡️ Sécurité opérationnelle

Voir [OPERATIONS.md](./OPERATIONS.md) pour les standards de pré-checks, post-checks
et procédure de récupération en cas de crash.

---

## 📝 Licence

MIT — voir [LICENSE](./LICENSE).
