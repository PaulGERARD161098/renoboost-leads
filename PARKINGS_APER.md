# Module Parkings loi APER

Ingère un **inventaire de parcs de stationnement extérieurs**, isole ceux soumis
à l'**obligation de solarisation** (article 40 de la loi APER), les enrichit via
le pipeline RénoBoost existant (L2 SIREN + L3 contacts + L4 scoring Claude) et
produit une liste de prospects *contraints et datés* pour l'installation
d'**ombrières photovoltaïques + bornes de recharge VE**.

> Indépendant du module `veille_immatriculations` : les deux tournent séparément.

## Pourquoi ce module

La loi APER (n°2023-175) + décret n°2024-1023 imposent aux parkings extérieurs
**> 1 500 m²** de couvrir **50 % de leur surface** d'ombrières photovoltaïques :

| Surface du parking | Échéance | Priorité |
|---|---|---|
| > 10 000 m² | **1er juillet 2026** | haute |
| 1 500 – 10 000 m² | **1er juillet 2028** | standard |

Sanction jusqu'à **40 000 €/an** par site non conforme. Chaque exploitant d'un
grand parking est donc un prospect **obligé** — le signal commercial le plus fort
pour Rossini Energy. Aucun outil du marché ne package ce ciblage clé-en-main.

## Architecture

```
inventaire_parkings.csv  →  parser_parkings  →  filtre_parkings (> seuil)
                                                       │
                                                       ▼
                                              etat_historique (flag déjà-vu)
                                                       │
                                                       ▼
                                              adaptateur_lead_l2
                                                       │
       LeadStage1 → EnricheurStage2 → EnricheurStage3 → EnricheurStage4
       (réutilise tout le pipeline RénoBoost existant ; contexte APER
        injecté dans le scoring L4)
                                                       │
                                                       ▼
                                                 LeadAper → CSV
```

## Source des données parkings

Le fichier d'entrée est un **inventaire géospatial** des parkings, à produire en
amont (hors module). Pistes :

1. **OpenStreetMap** — `amenity=parking` (export via [geodatamine.fr] ou
   l'extract `osm-france-parking-area` d'OpenDataSoft).
2. **IGN BD ORTHO** — mesure de surface par photo-interprétation / détection des
   lignes blanches sur les grands parcs.
3. **Fichier client** — un export maison (Excel/CSV) listant les parkings d'un
   foncier, d'une enseigne de retail, d'une foncière, etc.

Le module accepte n'importe quel CSV : le mapping de colonnes est paramétrable
(`AperConfig.mapping_colonnes`). Colonnes par défaut :

| Colonne fichier | Champ interne | Obligatoire |
|---|---|---|
| `SURFACE_M2` | `surface_m2` | ✅ |
| `IDENTIFIANT` | `identifiant` | — (sert au dédoublonnage) |
| `NOM` / `RAISON_SOCIALE` | `nom` / `raison_sociale` | — (matching SIREN) |
| `SIREN` | `siren` | — (si déjà connu) |
| `ADRESSE`, `CODE_POSTAL`, `COMMUNE`, `DEPARTEMENT` | idem | — |
| `LATITUDE`, `LONGITUDE` | idem | — |

Encodage défaut : `utf-8-sig` (BOM Excel). Séparateur : `;`.

## Utilisation CLI

### Dry-run (sans clé Anthropic, scores simulés)

```bash
python -m renoboost_leads.cli aper run \
  --fichier tests/fixtures_parkings/echantillon_parkings_demo.csv \
  --dry-run
```

### Mode normal (clé `ANTHROPIC_API_KEY` dans `.env`)

```bash
python -m renoboost_leads.cli aper run \
  --fichier inventaire_parkings.csv \
  --config config/client_rossini.yaml \
  --budget 2.0
```

### Options

| Option | Effet |
|---|---|
| `--surface-min 10000` | Ne garder que les parkings > 10 000 m² (échéance 2026) |
| `--config <yaml>` | Récupère `filtres_entreprise` + `claude_scoring` + nom client |
| `--source aper_ign` | Identifiant de source (traçabilité CSV) |
| `--dry-run` | Simulation L4 (aucun appel Anthropic) |

Sortie : `data/parkings_aper/<date>_<client>_<source>/parkings_aper_leads.csv`
avec toutes les colonnes L1+L2+L3+L4 + colonnes APER (surface, surface ombrable,
nb places estimé, échéance, priorité).

## Anti-doublon — flag-not-drop

Les parkings déjà traités lors d'un run précédent ne sont **pas exclus** : ils
sont marqués `deja_vu_parking=True`. État persistant partagé :
`data/parkings_aper/etat_parkings.sqlite`. Clé de dédoublonnage : `identifiant`
> `siren` > `nom+code_postal`.

## Scoring L4 contextualisé

Si le YAML ne fournit pas de `contexte_client`, le pipeline injecte
automatiquement un **contexte réglementaire APER** (offre Rossini + obligation
légale + échéances) pour que le score reflète l'urgence : grande surface +
échéance proche ⇒ score élevé.

## Tests

```bash
pytest tests/test_aper_*.py -v
```

Fixture : `tests/fixtures_parkings/echantillon_parkings_demo.csv` (10 parkings
représentatifs, dont 2 sous le seuil).

## Roadmap

| Phase | Statut | Contenu |
|---|---|---|
| A — Module + tests | ✅ | parser, filtre, état, adaptateur, pipeline, CLI, tests |
| B — Connecteur géospatial | ✅ | `aper geo` : extraction OSM/Overpass → CSV (surface réelle) |
| C — Matching renforcé | ✅ | géoloc parking → SIREN exploitant via `near_point` (`matching_geo.py`) ; flags `--no-geo` / `--rayon-geo` |
| D — Notification email | ✅ | résumé matinal post-run (`mailer.py`, réutilise `ConfigSMTP` + `envoyer_message` de la veille) ; flag `--no-email` |

**Phase C** se déclenche pour les parkings *sans enseigne ni SIREN* mais
géolocalisés : on interroge `recherche-entreprises/near_point` dans un petit
rayon (0,2 km par défaut) et on retient l'exploitant le plus plausible (effectif
le plus élevé parmi les plus proches), avant l'anti-doublon (l'identifiant stable
devient alors le SIREN). Le fallback Pappers/Societeinfo reste une évolution
possible si `near_point` ne suffit pas.

**Phase D** envoie un email récapitulatif (KPIs + top leads avec surface, échéance
et priorité APER + CSV joint) si SMTP est configuré (`SMTP_*` dans `.env`), sauf
`--no-email`.

[geodatamine.fr]: https://geodatamine.fr/
