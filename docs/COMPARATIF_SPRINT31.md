# Comparatif — plateforme RénoBoost vs sprint #31

> Analyse persistée le 2026-05-30. Situe les deux briques du sprint #31
> (parkings APER + enrichissement Societeinfo) par rapport au cœur existant de
> l'outil, et fonde l'étage de **complétion** générique (`src/renoboost_leads/completion/`).

## 1. Nature des choses comparées

| | **Outil existant** | **Sprint #31 (2 briques)** |
|---|---|---|
| Rôle | Colonne vertébrale : moteur de prospection B2B générique | Greffons branchés sur cette colonne |
| Modèle | *Push* : on part d'une recherche (secteur + zone) | APER = *pull réglementaire* ; SI = enrichissement à la demande |
| Maturité | Cœur stabilisé (700+ tests, multi-étages) | 2 modules neufs (~1 760 lignes, 38 tests) |

## 2. L'outil aujourd'hui — la « spine »

Pipeline en étages chaînés par héritage `LeadStage1 → 2 → 3 → 3.5 → 4` :

- **L0/L1** découverte (SIRENE-first + Google Places)
- **L2** appariement SIREN (data.gouv + fallback Pappers)
- **L3 / L3.5** contacts (scraping) + enrichissement Dropcontact
- **L4** scoring + pitch Claude

\+ modules satellites : **veille immatriculations VE** (source externe AAA Data),
**cold mail Instantly**, **agent conversationnel**, **storage Supabase**, **CLI RGPD**.

Caractéristique : *on choisit qui prospecter* (secteur/géo), l'outil qualifie.

## 3. Ce que le sprint ajoute

### a) `parkings_aper` — nouvelle porte d'entrée (origination)
N'utilise pas la découverte secteur/géo : ingère un **inventaire CSV de parkings**,
ne garde que ceux **> 1 500 m²** (seuil loi APER), puis **réutilise L2 + L3 + L4**.
Apport propre : échéance légale (2026/2028), priorité, surface ombrable, et
**contexte réglementaire injecté dans le scoring L4**. Le lead devient *contraint
et daté*. Calqué sur le patron `veille_immatriculations`.

### b) `societeinfo_enrichment` — porte latérale (qualité de donnée)
N'origine aucun lead : s'applique à **tout CSV de sortie** RénoBoost. Ciblage
coût-malin (`only_incertain`) : on ne paie l'API que là où le match SIREN gratuit
a échoué. À comparer au L3.5 Dropcontact (*contacts*) — Societeinfo couvre la
*firmographie + SIREN officiel*.

## 4. Insertion dans la chaîne de modèles

```
LeadStage1 → 2 → 3 → 3.5 → 4 → LeadVeille
                 └─ LeadSocieteinfo  (greffé en L2  → enrichissement)
                 └─ LeadComplete     (étage 3.7     → complétion générique)   ← ce sprint
                         LeadAper    (greffé en L4  → pipeline complet + colonnes parking)
```

## 5. Recouvrement & complémentarité

| Axe | Existant | APER | Societeinfo / Complétion |
|---|---|---|---|
| Origine du lead | recherche secteur/géo | inventaire parkings | (aucune — enrichit) |
| Réutilise L2/L3/L4 | — | oui, intégral | non (greffé) |
| Enrichissement payant | Dropcontact (contacts) | — | firmographie/SIREN |
| Anti-doublon persistant | par run | flag-not-drop SQLite | flag-not-drop |
| Déclencheur métier | offre commerciale | obligation légale datée | trou de donnée |

Aucune redondance : APER alimente le haut du tunnel, la complétion renforce le milieu.

## 6. De l'analyse à l'étage de complétion

Le point actionnable de cette analyse : ce que Societeinfo fait en commande
isolée mérite de devenir un **étage de pipeline générique**, utilisable dans
**toute génération de leads**, qui à la fois :

1. **enrichit** l'existant (NAF, effectif, CA, dirigeant, LinkedIn…), et
2. **repêche** ce que le pipeline classique (L1→L3.5) n'a pas trouvé
   (SIREN, dirigeant, email) via une source externe.

C'est l'objet de `src/renoboost_leads/completion/` (étage **3.7**, voir
[`COMPLETION.md`](../COMPLETION.md)) : interface provider swappable (1er provider =
Societeinfo), remplissage *fill-if-empty* des champs de base (qui traversent L4 et
le CSV final), provenance tracée, et **double livrable** par run — colonnes CSV
`completion_*` + fiche annexe `completion.md`.

## 7. Limites connues

- **APER** : dépend d'un CSV d'inventaire fourni (connecteur géospatial OSM/IGN = phase B) ;
  matching SIREN faible sans nom d'enseigne.
- **Societeinfo / complétion** : `_parse_resultat` à valider sur l'API réelle
  (`scripts/smoke_test_societeinfo.py`) ; dry-run par défaut sans clé.
- **Existant** : reste *push* — c'est ce que la porte APER vient compléter par un
  modèle *pull* réglementaire.
