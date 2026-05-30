# Étage de complétion (3.7) — repêchage & enrichissement

Étage **générique** branchable sur toute génération de leads. Il fait deux choses
à la fois, pour chaque lead :

1. **Enrichit l'existant** — ajoute la firmographie/contacts (NAF, effectif, CA,
   dirigeant, LinkedIn, téléphone…).
2. **Repêche** — va chercher via une source externe ce que le pipeline classique
   (L1→L3.5) n'a **pas** trouvé (SIREN, dirigeant, email).

Principe **fill-if-empty** : on ne réécrit jamais une valeur déjà trouvée par le
pipeline ; on ne comble que les trous, et on **trace la provenance**. **Flag-not-drop** :
aucun lead n'est supprimé.

## Position dans le pipeline

```
L3.5 (Dropcontact)  →  3.7 (Complétion)  →  L4 (scoring Claude)
```

Placé **avant L4** : le scoring profite des champs repêchés (SIREN, CA, dirigeant).
Comme la complétion comble les **champs de base** du modèle, ces valeurs traversent
L4 et le CSV final sans traitement particulier.

## Utilisation

```bash
# Dans un run standard (étage opt-in) :
renoboost run --config ma_campagne.yaml --stages 1,2,3,3.5,3.7,4

# Repartir d'un CSV L3/L3.5 existant :
renoboost run --config ma_campagne.yaml --stages 3.7 --from-csv data/output/<session>/etage3_contacts.csv

# Sans clé API → dry-run automatique (données simulées, zéro appel réseau) :
renoboost run --config ma_campagne.yaml --stages 3.7 --dry-run
```

## Provider

L'étage est **agnostique de la source** : il parle à un `ProviderCompletion`
(Protocol). Le 1er provider concret est **Societeinfo** (`SocieteinfoProvider`),
qui réutilise le client défensif de `societeinfo_enrichment`. D'autres providers
(Pappers, Dropcontact…) peuvent implémenter le même protocole sans toucher à l'étage.

Configuration : clé `SOCIETEINFO_API_KEY` dans `.env`. Absente → dry-run.

## Champs comblés (fill-if-empty)

| Champ de base | Source provider |
|---|---|
| `siren` | SIREN officiel |
| `dirigeant_nom`, `dirigeant_prenom`, `dirigeant_qualite` | dirigeant |
| `code_naf`, `libelle_naf` | activité |
| `tranche_effectif` | effectif |
| `chiffre_affaires` | CA |
| `emails_verifies` | emails |
| `telephone` | téléphone |
| `site_web` | site |
| `completion_linkedin` (champ dédié) | LinkedIn |

## Livrables (les deux)

1. **`etage3_7_completion.csv`** — toutes les colonnes du pipeline + colonnes
   `completion_*` : `completion_provider`, `completion_champs_remplis` (provenance),
   `cout_completion_eur`, `completion_erreur`.
2. **`completion.md`** — fiche annexe lisible : par lead repêché, ce qui a été
   comblé + une accroche prête pour le cold-mail.

## Ciblage & coût

Par défaut (`only_gaps=True`) : on n'appelle le provider **que** pour les leads à
trous (et hors `hors_filtre_entreprise`) → on ne paie que là où le gratuit a
échoué. Le coût est plafonné par le budget du run (`cfg.budget.max_eur`).

## Valider le provider sur l'API réelle

Le mapping `_parse_resultat` de Societeinfo suit la nomenclature documentée mais
**reste à confirmer sur le plan souscrit**. Un smoke-test réel est fourni :

```bash
python scripts/smoke_test_societeinfo.py [SIREN]
```

Pré-requis (dans une **nouvelle session**) : `societeinfo.com` ajouté à l'allowlist
réseau + `SOCIETEINFO_API_KEY` définie. Le script affiche la réponse **brute** à
comparer au mapping, et diagnostique un éventuel blocage allowlist.
