# Roadmap RénoBoost Leads

Document de suivi des chantiers ouverts. Mis à jour au fil des sessions.
Voir aussi `CLAUDE.md` (consignes session) et `CHANGELOG.md` (historique
des releases).

## Objectif court terme

Passer de **0% email pro / 0% tél direct dirigeant** à un taux qui
permet de lancer Instantly en cold-mail ciblé (≥ 40% email vérifié,
≥ 25% tél direct). Pour ça il faut activer les sources d'enrichissement
réelles et fiabiliser le matching SIREN.

## Chantiers sources de données

### P0 — Activer L3.5 Dropcontact en mode réel

> ✅ **Code livré** (étage 3.5 `stage3_5_enrichment` en prod, piloté par
> `DROPCONTACT_API_KEY` + flag `enable_stage_3_5_enrichment`). Reste opérationnel :
> fournir une clé valide et mesurer les taux sur une campagne pilote.

- Retirer `--dry-run` côté L3.5 dans la commande de run (laisser dry-run
  sur L4 si on ne veut pas encore consommer d'Anthropic).
- Tester sur 10 leads d'une campagne pilote (~5 € budget).
- Critères de succès :
  - email vérifié Dropcontact > 40%
  - tél direct dirigeant > 25%
- Si KO : on saura que Dropcontact ne couvre pas notre cible et il faut
  passer à Hunter (P2).

### P1 — Brancher l'API Pappers en L2 (en parallèle de Sirene)

> ✅ **Code livré** : fallback Pappers branché en L2 (compteurs
> `nb_fallback_pappers` / `cout_pappers_eur`), data.gouv en provider primaire
> gratuit. Reste opérationnel : `PAPPERS_API_KEY` valide (la clé actuelle
> renvoie 401 → fallback inopérant tant qu'elle n'est pas régénérée).

- Nouveau client `src/renoboost_leads/stage2_entreprises/pappers_client.py`
  à côté de l'existant `recherche_entreprises_client.py`.
- Match fuzzy par nom + CP/ville → débloque les leads que Sirene rate
  (ex: "Groupe Atlantic - Ygnis Industrie", "SHCI", "ASDI").
- Récupère les mandataires (gérant/président/DG) systématiquement →
  cible : passer de 30% à 85% sur "dirigeant identifié".
- Bonus pour le scoring L4 : CA, bilans, procédures collectives.
- Fallback Sirene si Pappers ne match pas (ne pas casser l'existant).
- Modèle éco : abonnement 49 €/mois illimité ou PAYG ~0.10 €/lead.

### P2 — Hunter.io en fallback L3 (si Dropcontact rate)

- À partir du domaine du site web, devine + vérifie les emails
  (`prenom.nom@dymatec-industries.com`).
- ~50 €/mois starter.
- À déclencher uniquement quand L3.5 Dropcontact a échoué pour ce lead.

### P3 — Apollo ou Phantombuster pour le tél direct dirigeant

- Scraping LinkedIn Sales Navigator → profil exact + tél direct +
  intitulé précis.
- 80-120 €/mois.
- À évaluer après P0/P1/P2 selon le taux atteint.

## Configs à séparer

La config actuelle `config/pilote_phase1.yaml` a une incohérence
interne : les queries L1 ("site industriel", "plateforme logistique")
ramènent des NAF en 10-33 / 52, mais le filtre `naf_inclus` est en
69-74 (tertiaire) → 100% des leads sont rejetés au passage L2→L3.

Cible : forker en deux YAML, chacun cohérent en interne.

- `config/pilote_phase1_tertiaire.yaml` :
  - queries L1 : comptables, avocats, archis, com, bureaux d'études
  - `naf_inclus`: ["69", "70", "71", "73", "74"]
- `config/pilote_phase1_industrie.yaml` :
  - queries L1 : sites industriels, plateformes logistiques, usines
  - `naf_inclus`: ["10","11","13","14","15","16","17","18","20","21",
    "22","23","24","25","26","27","28","29","30","31","32","33","52"]

Ajouter un test de cohérence interne (queries L1 ↔ NAF L2) au moment
du chargement du YAML — fail-fast plutôt que constater à la fin du run.

## Bugs UX du pipeline (à fixer en parallèle des sources)

- **Print L3 trompeur** : `✓ Étage 3 : 8 leads → etage3_contacts.csv`
  s'affiche alors que le CSV qualifié contient 0 ligne (8 leads en
  hors-filtre). Devrait afficher `0 qualifiés (8 hors filtre)` pour
  alerter immédiatement.
- **Warning manquant** quand `qualifiés=0 && hors_filtre>0` → signe
  quasi certain d'une incohérence secteurs L1 ↔ NAF L2. L'outil
  devrait dire en clair "config incohérente : tes queries L1 ramènent
  des entreprises dont aucun NAF n'est dans `naf_inclus`."
- **Verdict pilote indéterminé** : fixé en PR #16
  (`fix(report): verdict indéterminé + N/A quand session L3 vide`).
- **Dry-run L1 ignore la zone YAML** : `cli.py:_executer_stage1` génère
  des fake leads CP 13000 Marseille en dur, indépendamment de la zone
  configurée. À aligner sur la zone du YAML (générer des CP plausibles
  du département cible) pour que les tests dry-run aient un sens.

## Tableau récapitulatif coût/impact

| Priorité | Action | Impact attendu | Coût mensuel |
|---|---|---|---|
| P0 | Activer Dropcontact en réel | email 0→50%, tél direct 0→30% | ~50 €/100 leads |
| P1 | Brancher Pappers L2 | SIREN 70→95%, dirigeant 30→85% | 49 € flat ou ~10 € PAYG |
| P2 | Hunter en fallback L3 | email 50→70% | ~50 €/mois starter |
| P3 | Apollo/Phantombuster LinkedIn | tél direct 30→60% + intitulé | 80-120 €/mois |
