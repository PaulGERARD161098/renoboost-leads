# Coûts et limites — RénoBoost Leads

## Coûts API détaillés

### Étage 1 — Google Places API (New)

| Endpoint | Coût/req | Note |
|---|---|---|
| Text Search | 0.032 € | renvoie jusqu'à 20 résultats |
| Place Details (Pro) | 0.017 € | avec field mask optimisé |
| Place Details (Enterprise) | 0.020 € | tous les champs |

**Coût moyen par lead** : ~0.05-0.07 €
**Crédit gratuit Google** : 257 € sur 90 jours (suffit pour ~4000 leads)

### Étage 2 — Pappers API

| Plan | Prix mensuel | Requêtes incluses | Coût/req au-delà |
|---|---|---|---|
| Starter | 39 € | 100 | 0.10 € |
| Pro | 99 € | 1 000 | 0.08 € |
| Business | 299 € | 5 000 | 0.05 € |

**Coût moyen par lead enrichi** : ~0.10-0.15 €

### Étage 3 — Dropcontact

| Plan | Prix mensuel | Crédits |
|---|---|---|
| Starter | 49 € | 1 000 |
| Pro | 199 € | 5 000 |

**Coût moyen par lead enrichi** : ~0.05-0.20 €

### Étage 4 — Anthropic Claude API

| Modèle | Coût/lead (~500 tokens entrée + 200 sortie) |
|---|---|
| Haiku 4.5 | 0.005 € |
| Sonnet 4.6 (recommandé) | 0.02 € |
| Opus 4.7 | 0.10 € |

## Estimations par taille de run

### Run de validation (60 leads)
- Étage 1 seul : **~4 €**
- Étages 1+2 : ~11 €
- Étages 1+2+3 : ~23 €
- Pipeline complet : ~25 €

### Run client standard (200 leads)
- Étage 1 seul : ~12 €
- Pipeline complet : **~80 €** (+ 95 €/mois d'abos fixes)

### Run client large (500 leads)
- Pipeline complet : **~200 €** (+ 95 €/mois)

### Run massif (1000 leads)
- Pipeline complet : **~400 €** (+ 95 €/mois)

## ROI estimé (client ombrières solaires)

Hypothèses :
- Ticket moyen : 150 000 €
- Marge nette : 30 000 €
- Conversion lead → RDV : 1.5 %
- Conversion RDV → vente : 10 %

| Volume leads | Coût total run | RDV attendus | Ventes attendues | Marge brute | ROI |
|---|---|---|---|---|---|
| 200 | 80 € | 3 | 0.3 | 9 000 € | × 110 |
| 500 | 200 € | 7-8 | 0.75 | 22 500 € | × 110 |
| 1000 | 400 € | 15 | 1.5 | 45 000 € | × 110 |
| 2000 | 800 € | 30 | 3 | 90 000 € | × 110 |

⚠️ **Lecture honnête** : ces taux de conversion supposent une **bonne exécution commerciale** (séquence email pro, relances, cold call qualifié). Sans cela, comptez × 0.3 à × 0.5.

## Plafonds de sécurité

Les plafonds sont **hardcodés dans le code** ET réglables dans `.env` :

```env
MAX_BUDGET_EUR_PER_RUN=30      # Stop si dépassement (vérifié à chaque appel API)
MAX_LEADS_PER_RUN=500          # Stop si plus de N leads collectés
MAX_REQUESTS_PER_MINUTE=60     # Rate limit interne
```

L'outil **refuse de démarrer** si `estimate` dépasse `MAX_BUDGET_EUR_PER_RUN`.
