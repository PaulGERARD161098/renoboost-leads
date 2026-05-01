# Conformité RGPD — RénoBoost Leads

## Base légale invoquée

**Intérêt légitime (article 6.1.f RGPD)** : prospection commerciale B2B.

L'outil collecte exclusivement des **données professionnelles publiquement accessibles** :
- Données issues de Google Places (établissements publics)
- Données issues de Pappers (open data légal — registre du commerce)
- Données issues de Dropcontact (RGPD-compliant FR)

## Ce qui est autorisé

- ✅ Démarchage B2B par téléphone (sauf numéros inscrits à Bloctel)
- ✅ Email B2B à des contacts génériques (`contact@`, `info@`)
- ✅ Email à un décideur nominatif s'il est en lien avec ses fonctions et avec lien désinscription
- ✅ Stockage des données pour 3 ans maxi après dernier contact

## Ce qui est interdit

- ❌ Email vers particuliers (B2C) sans consentement
- ❌ Envoi sans lien de désinscription clair et fonctionnel
- ❌ Ignorer les demandes de suppression (droit à l'effacement)
- ❌ Revente des données collectées

## Mentions à inclure dans tout email envoyé

```
[Email professionnel envoyé via la base légale de l'intérêt légitime — RGPD art. 6.1.f]
Vos données nous proviennent de sources publiques (Google Places, registre du commerce).
Pour vous désinscrire ou exercer vos droits : <lien>
Responsable de traitement : [TON ENTREPRISE] — DPO : [email]
```

## Registre des traitements

À chaque run, l'outil génère automatiquement un fichier `registre_rgpd.md` dans le dossier de sortie, contenant :
- Date du traitement
- Sources des données
- Volume de leads collectés
- Finalité (prospection commerciale B2B pour [client])
- Durée de conservation prévue (3 ans max)

## Droit à l'effacement

Si une personne demande la suppression de ses données :
1. Identifier le lead par email/SIREN dans les CSV
2. Lancer `python -m renoboost_leads.cli forget --email <email>`
3. Documenter la demande dans `data/effacements_log.csv`

## Suppression automatique

Lancer trimestriellement :
```bash
python -m renoboost_leads.cli cleanup --older-than 3y
```
