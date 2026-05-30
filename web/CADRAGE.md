# Cadrage — Interface commerciale unique (CRM simple) pour RénoBoost-Leads

> **But du document** : spécifier de bout en bout l'interface web que va utiliser **Henri**
> (commercial, non-technicien) pour piloter la prospection du client **ReSign Énergie**,
> sans jamais toucher à Claude Code ni au YAML. Sert de référence partagée et de brief de
> construction pour livrer une **V1 complète d'un seul tenant**.
>
> Statut : **proposition à valider**. Aucune ligne de code applicatif n'est écrite avant feu vert.

---

## 1. Vision & utilisateurs

L'outil actuel est un **moteur** de prospection B2B (pipeline Python en 5 étages → CSV).
Il est puissant mais réservé à un profil technique. On lui ajoute une **couche interface**
qui transforme ce moteur en **produit commercial utilisable par n'importe qui**.

| Utilisateur | Rôle | Ce qu'il fait |
|---|---|---|
| **Paul** (toi) | Admin / pilote | Gère les cibles, supervise, garde la main sur le moteur |
| **Henri** | Commercial | Lance des recherches, traite les prospects, envoie, suit les réponses |

**Promesse produit** : *« Décris ta cible une fois, l'outil te livre des prospects qualifiés
avec un email prêt à envoyer, et tu suis tes réponses — le tout dans un seul écran simple. »*

Nom de travail : **ReSign CRM** (modifiable).

---

## 2. Principes de conception (CRM simple)

1. **Un écran = une tâche.** Pas de tableur à 40 colonnes. La tâche centrale d'Henri est une
   **file de prospects à traiter**, comme un triage d'emails.
2. **Divulgation progressive.** Le chemin quotidien est trivial (voir → valider → envoyer).
   Le « pilotage complet » (lancer une recherche, régler une cible) vit dans une zone
   *Avancé* séparée, sous forme de **formulaire guidé** — jamais de YAML ni de code NAF brut.
3. **Toute la tuyauterie est cachée.** Étages, verticales, codes NAF, Claude Code → invisibles.
   Henri voit des entreprises, des contacts, un mail, des boutons.
4. **Humain dans la boucle.** Aucun email ne part sans validation explicite (cohérent avec le
   staging cold-mail déjà codé).
5. **Mobile-friendly.** Henri consulte aussi en clientèle, sur téléphone.

---

## 3. Périmètre fonctionnel — les écrans

### 3.1 Connexion
Lien magique par email (Supabase Auth). 2 comptes au départ (Paul = admin, Henri = commercial).

### 3.2 Inbox / File des prospects  *(écran principal d'Henri)*
- Liste des leads **qualifiés**, triés par **score** décroissant.
- Chaque ligne : entreprise · ville · score · statut (pastille couleur).
- Filtres : statut, recherche/verticale, score min. Compteurs en tête (à traiter / envoyés / répondus).
- Clic → fiche prospect.

### 3.3 Fiche prospect  *(là où Henri passe 90 % du temps)*
- Bloc identité : entreprise, SIREN, secteur (libellé lisible, pas le code), effectif, ville, dirigeant.
- Bloc contact : email, téléphone, site.
- **Bloc email pré-rédigé, éditable** (sujet + corps), généré par l'étage 4.
- Actions : **Envoyer** (via Instantly) · **Modifier** · **Écarter** · **Oublier (RGPD)**.
- **Timeline d'activité** : créé, envoyé, ouvert, répondu, relancé.

### 3.4 Suivi / Pipeline
- Vue par statut : *à traiter · envoyés · ouverts · répondus · à relancer · écartés*.
- Sous forme de colonnes (kanban léger) ou table filtrable. Bouton « relancer » sur les sans-réponse.
- Indicateurs : taux d'ouverture, taux de réponse, leads restants.

### 3.5 Nouvelle recherche  *(formulaire guidé — pilotage)*
- Choix d'une **cible** parmi les verticales (presets lisibles : « Bornes IRVE flottes »,
  « Solaire toitures PME »…).
- **Zone** : sélecteur de département.
- **Taille d'entreprise** : curseur (ex. +50 salariés).
- **Budget plafond** : champ €.
- Bouton **Estimer** (coût + volume prévus) puis **Lancer**.
- **Avancement en direct** (étage en cours, leads trouvés) via Supabase Realtime.

### 3.6 Cibles / Verticales  *(admin — éditeur guidé)*
- Liste des verticales. Création/édition via **formulaire** (offre, secteurs, filtres, signaux,
  ton du mail, séquence) → écrit la structure `Verticale` validée. Jamais de YAML exposé.

### 3.7 Réglages
- Connexion Instantly (clé, expéditeur, signature/`from_email`).
- Gestion des utilisateurs.
- Registre RGPD consultable.

---

## 4. Architecture technique

```
   App web (Paul + Henri)            Base partagée             Moteur Python (existant)
   Next.js 15 (App Router)   ◄────►  Supabase Postgres   ◄────► run --verticale (839 tests)
   TypeScript · Tailwind ·           Auth · RLS · Realtime       + module storage déjà câblé
   shadcn/ui · Vercel                tables: leads/runs/...              ▲
        │                                                                │
        ├── Server Actions ──► API Instantly (envoi, clé côté serveur)   │
        └── « Lancer » ──► insère run_request ──────────► worker Python ─┘
                                                          (poll Supabase, exécute, écrit)
```

- **Front** : Next.js 15 (App Router, React Server Components, Server Actions), TypeScript,
  Tailwind + **shadcn/ui**, déployé sur **Vercel**.
- **Auth** : Supabase Auth (magic link), rôles via table `profiles`, **RLS** activé.
- **Base** : Supabase Postgres = **contrat** entre le moteur et l'app. Realtime pour
  l'avancement des runs et l'arrivée des leads.
- **Moteur** : pipeline Python inchangé, piloté par l'option `--verticale` déjà livrée.
- **Worker** : service Python (dossier `worker/`) qui **écoute** `run_requests`, construit une
  `CampaignConfig` depuis la verticale + zone choisies, exécute les étages 1→4, **pousse**
  l'avancement et les leads dans Supabase. Réutilise le module `storage` existant.

### Pourquoi un worker séparé
Vercel ne peut pas exécuter le pipeline (Python lourd, longue durée, appels Google/Claude).
Le worker tourne sur un hôte « toujours allumé » (Railway / Render / Fly / une VM), avec les
clés API. Couplage faible : l'app ne parle jamais au worker en direct, tout passe par Supabase.

---

## 5. Modèle de données Supabase

> Le modèle est le **contrat** moteur ↔ app. Les colonnes reflètent les modèles pydantic existants.

**`profiles`** — `id (uuid, =auth.users)`, `email`, `role (admin|commercial)`, `created_at`.

**`verticales`** — `id`, `slug (unique)`, `nom`, `description`, `config (jsonb` = structure
`Verticale` validée)`, `active (bool)`, `created_by`, `timestamps`.

**`runs`** — `id`, `verticale_id (fk)`, `zone (jsonb)`, `volume_cible`, `budget_eur`,
`status (demandé|en_cours|terminé|échoué)`, `etape_courante`, `progress (int %)`,
`counts (jsonb {l1,l2,l3,qualifiés})`, `cout_eur`, `log_url`, `created_by`, `timestamps`.

**`leads`** — `id`, `run_id (fk)`, `verticale_id (fk)`, `entreprise`, `siren`, `naf`,
`libelle_naf`, `effectif`, `ville`, `code_postal`, `score (int)`, `contact_nom`,
`contact_email`, `contact_tel`, `site_web`, `hors_filtre (bool)`, `raison_hors_filtre`,
`mail_sujet`, `mail_corps`, `statut (nouveau|à_valider|validé|envoyé|ouvert|répondu|à_relancer|écarté)`,
`instantly_id`, `sent_at`, `opened_at`, `replied_at`, `owner`, `timestamps`.

**`lead_events`** — `id`, `lead_id (fk)`, `type (créé|envoyé|ouvert|répondu|relancé|écarté|note)`,
`payload (jsonb)`, `at`. → alimente la timeline + l'audit RGPD.

**RLS** : commercial lit/écrit les leads de son périmètre ; admin voit tout. Clé `service_role`
réservée au worker (jamais exposée au front).

---

## 6. Intégration moteur (worker)

1. Henri lance une recherche → l'app insère une ligne `runs` (status `demandé`).
2. Le worker (boucle de poll ou Realtime) prend le run, le passe `en_cours`.
3. Il dérive une `CampaignConfig` : opérationnel (zone, volume, budget) + **ciblage depuis la
   verticale** (réutilise `_appliquer_verticale`).
4. Il exécute les étages 1→4 ; à chaque étape il met à jour `runs.progress/etape_courante/counts/cout_eur`.
5. Il **upsert** les leads (avec mail rédigé en étage 4) dans `leads`, status `nouveau`.
6. Fin → `runs.status = terminé`. L'app affiche les nouveaux leads en temps réel.

Aucune modification cassante du moteur : on ajoute un point d'entrée `worker/` qui réutilise
l'existant (`config`, étages, `storage`).

---

## 7. Envoi & suivi (Instantly)

- **Envoi** : Server Action côté Next.js → API Instantly (clé serveur). Réutilise le concept de
  **staging** déjà codé + validation humaine. Au succès : `leads.statut = envoyé`, `sent_at`,
  `instantly_id`, event `envoyé`.
- **Suivi** : webhook Instantly (ouvertures/réponses) → endpoint Next.js → met à jour
  `opened_at/replied_at/statut` + events. (Fallback : polling périodique si pas de webhook.)
- **Pré-requis délivrabilité** (ops) : domaine d'envoi dédié + SPF/DKIM/DMARC + warm-up. Hors code.

---

## 8. Sécurité & RGPD

- Clés API **toujours côté serveur** (worker = `service_role` ; front = `anon` + RLS).
- RGPD : le moteur a déjà **registre** + **droit à l'effacement**. Bouton « Oublier ce lead »
  → déclenche la purge ; chaque action est tracée dans `lead_events` (auditabilité).
- Auth obligatoire, rôles, RLS. Pas de donnée prospect accessible sans connexion.

---

## 9. Plan de construction (jalons, livrés d'un bloc)

| Jalon | Contenu | Sortie vérifiable |
|---|---|---|
| **M0** | Provisionner Supabase (projet + schéma + RLS) ; scaffold Next.js dans `web/` ; projet Vercel ; CI. | App qui démarre, base en ligne |
| **M1** | Auth + Inbox + Fiche prospect (lecture leads). | Henri se connecte, voit/ouvre des leads |
| **M2** | Envoi Instantly + statuts + timeline + écran Suivi. | Henri envoie et suit ses réponses |
| **M3** | Worker Python + écran *Nouvelle recherche* + avancement live. | Henri lance un run et voit les leads tomber |
| **M4** | Éditeur de verticales + Réglages + RGPD + indicateurs. | Pilotage complet |
| **M5** | Polish mobile, tests e2e, déploiement prod, doc Henri. | Prod utilisable + guide 1 page |

Même si tout est livré ensemble, la construction suit cet ordre pour rester vérifiable à chaque étape.

---

## 10. Brief de construction (« prompt précis »)

> À utiliser pour lancer la construction (ou la reprendre dans une session neuve).

```
Construis "ReSign CRM" : interface web commerciale au-dessus du moteur de prospection
RénoBoost-Leads (pipeline Python existant, piloté par `run --verticale <slug>`).

STACK : Next.js 15 (App Router, Server Components, Server Actions) + TypeScript + Tailwind
+ shadcn/ui, déployé sur Vercel. Base = Supabase (Postgres + Auth magic link + RLS + Realtime).
Worker Python séparé (dossier worker/) qui écoute Supabase et exécute le pipeline.
L'app vit dans web/ du repo renoboost-leads.

UTILISATEURS : Paul (admin), Henri (commercial, non-technicien). RLS par rôle.

ÉCRANS (cf. cadrage §3) :
  1. Connexion (magic link)
  2. Inbox des prospects qualifiés (tri par score, filtres statut/verticale, compteurs)
  3. Fiche prospect (identité + contact + email éditable + Envoyer/Modifier/Écarter/Oublier
     + timeline d'activité)
  4. Suivi/Pipeline (statuts, taux ouverture/réponse, relances)
  5. Nouvelle recherche (formulaire guidé : verticale + département + taille + budget,
     bouton Estimer puis Lancer, avancement live via Realtime)
  6. Cibles/Verticales (éditeur guidé en formulaire → structure Verticale validée, jamais de YAML)
  7. Réglages (Instantly, expéditeur/signature, utilisateurs, registre RGPD)

DONNÉES SUPABASE (cf. cadrage §5) : profiles, verticales, runs, leads, lead_events. RLS activé.
service_role réservé au worker.

INTÉGRATION MOTEUR (cf. §6) : le worker prend un `runs` en status 'demandé', dérive une
CampaignConfig (opérationnel via la config + ciblage via `_appliquer_verticale`), exécute les
étages 1→4, pousse progress/counts/cout dans `runs`, upsert les leads (avec mail étage 4) dans
`leads`. Réutilise le module storage existant. Ne casse aucun test du moteur (839 passed / ruff clean).

ENVOI (cf. §7) : Server Action → API Instantly (clé serveur), validation humaine obligatoire.
Webhook Instantly → maj opened/replied/statut.

UX (cf. §2) : un écran = une tâche ; divulgation progressive (pilotage avancé séparé) ; aucune
tuyauterie exposée ; mobile-friendly ; aucun envoi sans validation explicite.

SÉCURITÉ/RGPD (cf. §8) : clés côté serveur, RLS, bouton Oublier (purge + trace lead_events).

LIVRABLE : app déployée sur Vercel + worker documenté, guide Henri 1 page. Tests e2e des
parcours clés (connexion, traiter un lead, envoyer, lancer une recherche).
```

---

## 11. Pré-requis & secrets

| Élément | Statut | Action |
|---|---|---|
| Projet Supabase | à créer | **Je le provisionne** (outils dispo) |
| Projet Vercel | à créer | **Je le provisionne** (outils dispo) |
| Clé API **Instantly** | absente de l'env | À fournir (sinon envoi en **mode simulation**) |
| Clés Google/Pappers/Dropcontact/Anthropic | présentes (Pappers à recharger) | Pour le worker |
| Domaine d'envoi + SPF/DKIM/DMARC + warm-up | à préparer | Ops, hors code |

---

## 12. Risques & décisions ouvertes

- **Hébergement du worker** : Vercel ne peut pas l'exécuter. À choisir (Railway / Render / Fly /
  VM). Décision avant M3.
- **Délivrabilité email** : sans domaine chaud + SPF/DKIM, les envois finissent en spam. À
  préparer en parallèle (ops).
- **Crédits Pappers** : épuisés (401). data.gouv couvre ~50 % des SIREN ; recharger pour le reste.
- **Périmètre V1** : « tout d'un bloc » est ambitieux ; les jalons M0→M5 permettent de livrer et
  vérifier par paliers tout en visant une V1 complète.
```
