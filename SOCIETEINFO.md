# Enrichissement Societeinfo

Module d'**enrichissement firmographique** via l'API [Societeinfo], qui s'appuie
sur les registres officiels FR (INSEE / BODACC / INPI). Meilleur taux de match
SIREN + firmographie que le L2 gratuit (data.gouv).

> **Indépendant** : s'utilise seul, sur n'importe quel CSV de sortie RénoBoost,
> via la commande `enrich-societeinfo`. Aucune modification du pipeline principal
> n'est requise.

## Quand l'utiliser

Le L2 gratuit (data.gouv) couvre 70-85 % des matchs SIREN. Pour les leads
restants (match absent ou incertain), Societeinfo monte à ~92-95 % et ajoute CA,
dirigeant, contacts. Stratégie recommandée : **payer la qualité seulement là où
le gratuit a échoué** (mode par défaut `only_incertain`).

| Métrique | L2 gratuit | + Societeinfo |
|---|---|---|
| Taux match SIREN | 70-85 % | 92-95 % |
| CA / effectif | tranche INSEE | CA exact (selon plan) |
| Dirigeant + contacts | principal | enrichis |

## Utilisation CLI

### Ciblage intelligent (défaut : SIREN manquant ou incertain)

```bash
python -m renoboost_leads.cli enrich-societeinfo \
  --from-csv data/output/<session>/etage2_entreprises.csv
```

### Enrichir TOUS les leads (mode « base de données »)

```bash
python -m renoboost_leads.cli enrich-societeinfo \
  --from-csv <leads>.csv --all --budget 20
```

### Dry-run (données simulées, aucun appel réseau)

```bash
python -m renoboost_leads.cli enrich-societeinfo --from-csv <leads>.csv --dry-run
```

> Sans `SOCIETEINFO_API_KEY` dans `.env`, la commande bascule **automatiquement
> en dry-run** (avec avertissement) — tout le câblage est testable sans abo.

### Options

| Option | Effet |
|---|---|
| `--from-csv <path>` | CSV d'entrée (L1, L2, L3...) — **requis** |
| `--out <path>` | CSV de sortie (défaut : `<input>_societeinfo.csv`) |
| `--all` | Enrichit tous les leads (sinon : seulement SIREN absent/incertain) |
| `--budget <eur>` | Plafond budgétaire (BudgetGuard) |
| `--dry-run` | Données simulées |

## Sortie

Le CSV de sortie reprend toutes les colonnes L2 + un bloc `societeinfo_*` :

```
societeinfo_siren, societeinfo_naf, societeinfo_libelle_naf,
societeinfo_effectif, societeinfo_chiffre_affaires, societeinfo_dirigeant,
societeinfo_email, societeinfo_emails, societeinfo_telephone,
societeinfo_site_web, societeinfo_linkedin,
enrichi_societeinfo, societeinfo_erreur, cout_societeinfo_eur
```

**Flag-not-drop** : aucun lead n'est supprimé. Le SIREN manquant d'un lead est
comblé par celui de Societeinfo quand trouvé.

## Configuration

```env
# .env
SOCIETEINFO_API_KEY=...
```

Le endpoint et le coût/lead sont paramétrables dans `SocieteinfoClientConfig`
(`base_url`, `endpoint`, `cout_par_lead_eur`).

⚠️ Le mapping des champs de réponse (`SocieteinfoClient._parse_resultat`) suit la
nomenclature documentée par Societeinfo ; **à reconfirmer contre la doc du plan
souscrit** avant la mise en production (le client est défensif : il tolère les
deux formes `result` / `results` et plusieurs alias de champs).

## Tests

```bash
pytest tests/test_societeinfo.py -v
```

[Societeinfo]: https://societeinfo.com/
