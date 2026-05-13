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

## Roadmap

| Phase | Statut | Contenu |
|---|---|---|
| A — Squelette + tests | ✓ | Parser, filtre, état, adaptateur, pipeline, mailer, CLI, tests |
| B — Validation manuelle | en attente d'échantillon | Adapter le parser au format réel AAA + qualité du tri |
| C — Automatisation | à venir | Connecteur SFTP, cron quotidien, notification email, intégration Streamlit |

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
