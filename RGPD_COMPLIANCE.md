# Conformité RGPD — RénoBoost Leads

## Base légale invoquée

**Intérêt légitime (article 6.1.f RGPD)** : prospection commerciale B2B.

L'outil collecte exclusivement des **données professionnelles publiquement accessibles** :
- Données issues de Google Places (établissements publics)
- Données issues de Pappers (open data légal — registre du commerce)
- Données issues de Dropcontact (RGPD-compliant FR)
- Scoring via Anthropic Claude (sous-traitant — voir section dédiée)

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

Sur demande de suppression, utiliser la commande dédiée :

```bash
# Aperçu sans modification (recommandé d'abord)
python -m renoboost_leads.cli forget --email contact@exemple.fr --dry-run

# Effacement réel
python -m renoboost_leads.cli forget --email contact@exemple.fr --motif "demande client X"
# ou par SIREN / place_id
python -m renoboost_leads.cli forget --siren 123456789
python -m renoboost_leads.cli forget --place-id ChIJxxxxx
```

La commande :
- balaie toutes les sessions sous `data/output/<session>/`
- efface les lignes matchant dans chaque `etage*.csv` (qualifiés, hors-filtre,
  L3.5 Dropcontact, L4 prospection) **et leurs backups horodatés**
- purge les caches SQLite associés (`cache.sqlite`, `cache_l3_5.sqlite`,
  `cache_l4.sqlite`) sur les `place_id` concernés
- inscrit la demande dans `data/effacements_log.csv` (date ISO 8601, type
  d'identifiant, valeur, sessions touchées, lignes effacées, motif)

## Suppression automatique des sessions anciennes

Commande dédiée — **dry-run par défaut** pour éviter toute perte accidentelle :

```bash
# Lister les sessions > 3 ans (défaut)
python -m renoboost_leads.cli cleanup

# Lister avec un seuil custom
python -m renoboost_leads.cli cleanup --older-than-days 90

# Archiver (tar.gz dans data/archives/) puis supprimer
python -m renoboost_leads.cli cleanup --mode archive

# Supprimer directement sans archive
python -m renoboost_leads.cli cleanup --mode delete
```

Recommandation CNIL en prospection B2B : 3 ans. Câbler en cron pour automatiser
(`0 3 1 */3 *` = tous les 1ers du trimestre à 3h du matin).

## Étage 4 — sous-traitance Anthropic (Claude)

L'étage 4 envoie pour chaque lead un prompt contenant des **données publiques B2B**
(nom commercial, NAF, effectif, dirigeant identifié, emails publics scrapés) à l'API
Anthropic pour obtenir un score d'intérêt et un pitch.

### Statut sous-traitant

- **Responsable de traitement** : utilisateur RénoBoost Leads (toi).
- **Sous-traitant** : Anthropic PBC (siège San Francisco, US).
- **Base légale** : article 28 RGPD (sous-traitance).
- **Localisation traitement** : centres de données US (et UE selon routage Anthropic).
- **Transferts internationaux** : couverts par les **Standard Contractual Clauses (SCC)**
  signées entre le client et Anthropic dans l'**Anthropic DPA** (Data Processing Agreement,
  https://www.anthropic.com/legal/dpa).

### Engagements Anthropic vérifiés

- ❌ Les données envoyées via l'API ne sont **pas utilisées pour entraîner** les modèles
  (paramètre par défaut — voir privacy.anthropic.com).
- 🗑 Rétention par défaut : ~30 jours pour la modération de contenu, puis suppression.
- 🔒 Chiffrement en transit (TLS) et au repos.

### Actions requises avant utilisation en production

1. **Accepter le DPA Anthropic** depuis la console (https://console.anthropic.com).
2. Tenir à jour le **registre des traitements** côté responsable (article 30).
3. Documenter dans la **politique de confidentialité client** la mention :
   _"Vos données professionnelles peuvent être traitées par Anthropic PBC (sous-traitant
   technique, US) dans le cadre de l'évaluation qualitative de prospects, sous régime
   RGPD article 6.1.f (intérêt légitime) et SCC pour le transfert international."_
4. Pour les clients soumis à exigences souveraines fortes (santé, défense), **désactiver
   L4** (`--stages 1,2,3`) et faire le scoring manuel.
