# Runbook de mise en production — RénoBoost Leads

Procédures **OPS** pour activer et vérifier les briques en production. Chaque
section liste : *ce qu'il faut faire* (console externe — action humaine), puis
*comment vérifier* (depuis le code / Supabase). Le code moteur n'a rien à changer
pour ces bascules — ce sont des variables d'environnement et des activations de
comptes tiers.

> Sécurité : ne **jamais** committer ni logguer une clé API réelle. Toutes les
> clés se posent dans les variables d'environnement de la plateforme (Railway,
> Vercel, Supabase), pas dans le dépôt.

---

## 1. Worker réel sur Railway (`WORKER_MODE=real`)

Transforme les `runs` Supabase en vrais `leads` via le moteur L1→L4.

### À faire (Railway → service worker → Variables)

Obligatoires :

| Variable | Valeur |
|---|---|
| `SUPABASE_URL` | URL du projet (`https://gkvpvuipxyafvbwnqbab.supabase.co`) |
| `SUPABASE_SERVICE_ROLE_KEY` | clé **service_role** (pas `anon`) |
| `WORKER_MODE` | `real` |
| `GOOGLE_PLACES_API_KEY` | clé Google Places (L1) |
| `ANTHROPIC_API_KEY` | clé Anthropic (L4) |

Optionnelles (sinon l'étage est sauté / dégradé) :

| Variable | Effet |
|---|---|
| `DROPCONTACT_API_KEY` | active L3.5 (enrichissement contacts) |
| `PAPPERS_API_KEY` | fallback firmographique L2 (sinon data.gouv seul) |
| `SOCIETEINFO_API_KEY` | provider L2/L3.7 registres officiels |
| `MAX_BUDGET_EUR_PER_RUN` | plafond budget/run (défaut 50) — mettre bas pour les premiers essais |
| `MAX_LEADS_PER_RUN` | plafond leads/run (défaut 500) |
| `CLAUDE_MODEL` | modèle L4 (défaut Haiku 4.5) |

Puis **Redeploy**. Vérifier que le déploiement passe bien par le **Dockerfile
worker** (#46) et non un build générique.

> Garde-fou : en `real`, si `GOOGLE_PLACES_API_KEY` **ou** `ANTHROPIC_API_KEY`
> manque, le run est marqué `echoue` avec un message clair **sans consommer de
> crédit**. L2 (data.gouv) est gratuit.

### Comment vérifier

1. **Logs Railway** : au démarrage le worker annonce son mode ; en boucle il
   poll toutes les 5 s (visible aussi côté Supabase, service `api`, requêtes
   `python-requests` sur `runs`).
2. **Essai contrôlé** : créer un petit run depuis le CRM (ex. *Solaire PME
   toitures*, dépt 59, budget 5 €, volume 10) et suivre la transition de statut
   `demande → en_cours → termine`, puis l'apparition des `leads` (avec
   coordonnées + `code_naf`/`libelle_naf`).
3. **Requête de contrôle Supabase** (lecture seule) :
   ```sql
   select id, status, progress, etape_courante, erreur, created_at
   from runs order by created_at desc limit 5;
   select count(*), min(score_global), max(score_global)
   from leads where run_id = '<id_du_run>';
   ```

---

## 2. Batch satellite (analyse potentiel solaire)

Analyse IGN + Claude Vision en tâche de fond sur les leads, après un run.

### À faire (Railway → worker → Variables)

| Variable | Valeur | Rôle |
|---|---|---|
| `WORKER_SATELLITE` | `true` | active le batch satellite |
| `WORKER_SATELLITE_MAX` | `60` (défaut) | nb max de leads analysés / cycle |
| `WORKER_SATELLITE_MODEL` | `claude-haiku-4-5` (défaut) | modèle vision |

### Comment vérifier

Après un run, les leads se voient attribuer un potentiel solaire / score foncier ;
l'onglet satellite du CRM se peuple. Logs worker : lignes `satellite`.

---

## 3. Veille d'intentions web (web search Anthropic)

L'onglet *Veille* (CRM, #59) s'appuie sur l'outil **web search** d'Anthropic.

### À faire

1. **Console Anthropic** : activer l'outil *web search* sur le compte/clé
   utilisé en prod (prérequis — sans cela l'appel échoue).
2. Vérifier que la `ANTHROPIC_API_KEY` du déploiement web (Vercel) est celle du
   compte où web search est activé.

### Comment vérifier

CRM → onglet *Veille* → **Lancer la veille** : des signaux (VE / ombrières /
électrification) doivent remonter. En cas d'erreur d'outil, c'est que web search
n'est pas activé côté compte.

---

## 4. Délivrabilité e-mail + cold mailing (Instantly)

Pour passer le cold-mail de la simulation à l'envoi réel.

### À faire — délivrabilité (prérequis, indépendant du code)

1. **Domaine d'envoi dédié** (ne pas brûler le domaine principal).
2. **SPF / DKIM / DMARC** configurés sur ce domaine.
3. **Warm-up** progressif du domaine avant volume.

### À faire — Instantly (variables d'env du service concerné)

| Variable | Rôle |
|---|---|
| `INSTANTLY_API_KEY` | bascule l'envoi de simulation → réel |
| `INSTANTLY_WEBHOOK_SECRET` | vérification des webhooks entrants |
| `INSTANTLY_DRY_RUN` | passer à `false` pour l'envoi réel (défaut `true`) |

Configurer aussi le **webhook Instantly** vers l'endpoint prévu.

### Comment vérifier

Sans `INSTANTLY_API_KEY`, le staging cold-mail reste en **simulation**
(`instantly_dry_run=true`). Avec la clé et `INSTANTLY_DRY_RUN=false`, les envois
partent réellement — valider d'abord sur une cible interne réduite.

---

## 5. Notification email post-run (SMTP) — veille & parkings APER

Les pipelines *veille immatriculations* et *parkings APER* envoient un
récapitulatif matinal si SMTP est configuré (sinon : pas d'envoi, silencieux).

### À faire (`.env` / variables du service)

| Variable | Exemple |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | `compte@domaine.fr` |
| `SMTP_PASSWORD` | mot de passe d'application |
| `SMTP_FROM` | `veille@domaine.fr` |
| `SMTP_DESTINATAIRES` | `a@x.fr,b@x.fr` (CSV) |
| `SMTP_USE_TLS` | `true` |

### Comment vérifier

Lancer un run `aper run` (ou `veille run`) avec SMTP renseigné → un email
récapitulatif (KPIs + top leads + CSV joint) arrive. Désactivation ponctuelle :
`--no-email`.

---

## 6. Ménage prod (cosmétique)

- Supprimer le projet Railway doublon (`upbeat-commitment`) s'il existe encore.
- Purger les vieux déploiements Vercel en échec (rouge) — sans impact fonctionnel.
