# Veille immatriculations VE flotte

Module pour ingérer le **flux quotidien AAA Data** des immatriculations de véhicules
électriques en flotte entreprise, l'enrichir via le pipeline RénoBoost existant
(L2 SIREN + L3 contacts + L4 scoring Claude), et notifier le client par email.

## Pourquoi ce module

Une entreprise qui s'électrifie sa flotte est un **signal commercial fort** pour
la rénovation thermique : démarche transition énergétique active = budget capex =
décisionnaire identifié. Le client RénoBoost reçoit chaque matin un fichier AAA
Data, et nous le branchons automatiquement sur le pipeline.

## Architecture

```
fichier_aaa.csv  →  parser_aaa  →  filtre_ve_flotte  →  etat_historique
                                                           │
                                                           ▼
                                                  adaptateur_lead_l2
                                                           │
       LeadStage1 → EnricheurStage2 → EnricheurStage3 → EnricheurStage4
       (réutilise tout le pipeline RénoBoost existant)
                                                           │
                                                           ▼
                                                     LeadVeille → CSV
                                                                  │
                                                                  ▼
                                                                mailer
                                                                  │
                                                                  ▼
                                                           email matinal
```

## Source : AAA Data

Opérateur officiel de diffusion commerciale des données du SIV (Système
d'Immatriculation des Véhicules). Pour activer :

1. Contact commercial AAA Data → souscription flux quotidien VE flotte
2. Choisir le canal de livraison **SFTP** (recommandé)
3. Pré-filtrage côté serveur si possible : énergie ∈ {EL/HE/HH} + personne morale
4. Demander un **échantillon CSV** avant signature pour valider la structure

### Colonnes attendues (convention standard, ajustable)

Le mapping est paramétrable via `VeilleConfig.mapping_colonnes`. Par défaut :

| Colonne fichier | Champ interne | Notes |
|---|---|---|
| `DATE_IMMATRICULATION` | `date_immatriculation` | YYYY-MM-DD, fallback DD/MM/YYYY |
| `PLAQUE` | `plaque` | optionnel |
| `MARQUE`, `MODELE` | `marque`, `modele` | |
| `ENERGIE` | `energie` | EL, HE, HH, EH, H2 = VE retenus |
| `TYPE_VEHICULE` | `type_vehicule` | VP, VU, PL, CTTE |
| `TYPE_ACQUEREUR` | `type_acquereur` | M / PM = personne morale retenue |
| `SIREN` | `siren` | SIRET accepté (auto-coupé aux 9 premiers chiffres) |
| `RAISON_SOCIALE` | `raison_sociale` | |
| `CODE_POSTAL`, `COMMUNE`, `DEPARTEMENT` | idem | CP padded à 5 chiffres |

Encodage par défaut : `utf-8-sig` (gère BOM Excel). Séparateur : `;`.

## Utilisation CLI

### Mode dry-run (sans clé Anthropic, scores simulés)

```bash
python -m renoboost_leads.cli veille run \
  --fichier exemple_aaa_2026-05-13.csv \
  --dry-run
```

### Mode normal (avec clé Anthropic dans `.env`)

```bash
python -m renoboost_leads.cli veille run \
  --fichier exemple_aaa_2026-05-13.csv \
  --config config/client_renoboost.yaml \
  --budget 2.0
```

Sortie : `data/veille/<date>_<client>_<source>/veille_leads.csv` avec toutes les
colonnes L1+L2+L3+L4+veille.

## Anti-doublon — stratégie flag-not-drop

Les SIREN déjà observés en VE auparavant ne sont **pas exclus**. Ils sont
marqués `deja_eu_ve=True` et `premiere_date_ve=<date>` dans le CSV. Ainsi tu
gardes la visibilité sur les ré-acquisitions tout en pouvant filtrer côté lecture
si besoin.

État persistant : `data/veille/etat_siren_ve.sqlite` — partagé entre tous les
runs. Pour réinitialiser : `rm data/veille/etat_siren_ve.sqlite`.

## Notification email (Phase C)

Squelette posé dans `mailer.py`. Config via `.env` (à ajouter) :

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=veille-renoboost@gmail.com
SMTP_PASSWORD=<mot_de_passe_application_gmail>
SMTP_FROM=veille-renoboost@gmail.com
SMTP_DESTINATAIRES=paul@renoboost.fr,co@renoboost.fr
```

Le mail contient :
- Résumé KPIs (lignes brutes, VE flotte, nouveaux, déjà vus, top leads, coût L4)
- Tableau HTML des 5 premiers top leads
- CSV complet en pièce jointe

**Branchage cron** non fait en Phase A — à activer une fois le flux validé
manuellement sur quelques fichiers réels.

## Parser CSV générique (auto-détection)

Si le fichier source n'est pas garanti format AAA (export client maison, autre source),
utilise `parser_generique.py` qui :
- Détecte automatiquement l'**encodage** (utf-8 / utf-8-sig / latin-1 / cp1252)
- Détecte automatiquement le **séparateur** (`;` `,` `|` `\t`)
- Propose un **mapping intelligent** des colonnes vers les champs internes (matching
  insensible à la casse / accents / espaces)
- Liste les **champs obligatoires manquants** et les colonnes inconnues

Utilisable directement depuis l'UI Streamlit (onglet **📥 Nouveau run**) avec
mapping interactif des colonnes incertaines.

## Notification email automatique

Une fois `SMTP_*` configurés dans `.env`, l'email est envoyé **automatiquement
post-run** par la CLI et par le cron GitHub Actions. Désactivable avec `--no-email`.

## Cron quotidien (GitHub Actions)

Le workflow `.github/workflows/veille_quotidienne.yml` lance la veille tous les
matins (lun-ven, 07:30 UTC).

**Setup une seule fois** :
1. Place le fichier AAA du jour dans `data/veille_inbox/aaa_jour.csv` (ou autre
   chemin configurable, manuellement ou via SFTP push)
2. Configure les **secrets GitHub** dans Settings → Secrets and variables → Actions :
   - `ANTHROPIC_API_KEY`
   - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`,
     `SMTP_DESTINATAIRES`
3. Active le workflow (par défaut activé après merge)

**Déclenchement manuel** : Actions → Veille quotidienne → **Run workflow**
(possibilité d'override le fichier d'entrée + dry-run).

Les artefacts (CSV final + logs) sont uploadés sur l'exécution GitHub Actions
(rétention 30 jours).

## Roadmap

| Phase | Statut | Contenu |
|---|---|---|
| A — Squelette + tests | ✅ | Parser, filtre, état, adaptateur, pipeline, mailer, CLI, tests |
| B — Validation manuelle | en attente d'échantillon AAA | Adapter le parser au format réel + qualité du tri |
| C — Automatisation | ✅ | Mailer branché auto + cron GitHub Actions + UI Streamlit upload |
| D — Connecteur SFTP push | à venir | Auto-pull du fichier AAA depuis SFTP avant lancement |

## RGPD

Les immatriculations sont des **données publiques** (le SIV en diffuse l'agrégat
via AAA Data sous licence commerciale). Pas de données personnelles côté
particuliers — uniquement personnes morales. Conformité B2B identique au reste
du pipeline (voir `RGPD_COMPLIANCE.md`).

## Tests

```bash
pytest tests/test_veille_*.py -v
```

Fixture CSV : `tests/fixtures_aaa/echantillon_aaa_demo.csv` (10 lignes
représentatives, ajustable quand l'échantillon réel arrive).
