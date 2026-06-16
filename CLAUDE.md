# CLAUDE.md — consignes session Claude Code

## 🛡️ Pannes connues & doctrine anti-régression (mémoire — lire à CHAQUE session)

**Fil rouge de toutes les pannes vues : la DÉGRADATION SILENCIEUSE** — un run finit
« terminé » (vert) alors qu'il est cassé. Règle d'or : **jamais d'échec silencieux**.

**Catalogue des pannes (symptôme → cause → garde-fou en place) :**
1. **Run en boucle / PATCH 400 sur `/rest/v1/runs`** → migration non appliquée au
   live (ex. `runs.cout_detail`, migration 0036). *Garde-fou* : préflight schéma DB
   au boot worker (`Worker.preflight` → `verifier_colonnes_runs`). *Réflexe* : après
   un merge, vérifier `list_migrations` vs `web/supabase/migrations/`.
2. **Recherche « terminée » mais 0 prospect (coût 0 €)** → découverte vide. Cause
   vue : ciblage NAF en **divisions** (`"10"`) + `decouverte_sirene_first` ; l'API
   `recherche-entreprises` n'accepte que les **codes APE complets** (`25.11Z`).
   *Garde-fou* : `raison_degradation` flague `decouverte==0`/`leads==0`.
3. **Leads sans score ni mail (`claude=0 €`, `scores_ko>0`)** → étage 4 Claude en
   échec **silencieux**. Causes vues : **crédits Anthropic épuisés** (400
   `invalid_request_error` « credit balance too low »), id de modèle non daté.
   *Garde-fou* : préflight ping Claude + `resolve_model_id` + `scores_ko` dans
   `counts` + diagnostic dans `score_raison`/`runs.erreur`.

**Doctrine permanente (à appliquer sans qu'on le redemande) :**
- **Auto-check AVANT de lancer** : préflight worker au boot **et** pré-vérif par run
  réel (Claude joignable) — sinon échec immédiat avec diagnostic, **0 budget engagé**.
- **Toujours un diagnostic visible** : tout run qui ne tourne pas à 100% porte un
  message « où ça a coincé » (`runs.erreur` = étape + cause), affiché à l'UI
  (rouge=échec, ambre=dégradé) ; jamais un blanc.
- **`worker_heartbeat.last_error` est tronqué à 80 car. dans l'UI** : toujours lire
  la valeur **complète** en base avant de conclure (un « …supabase.co/ » trompeur
  cachait `/rest/v1/runs?id=...`).
- **Ne pas surcharger `runs.qualite`** : c'est la note **manuelle** de l'utilisateur
  (bonne/moyenne/mauvaise), pas un canal de diagnostic.
- **Magellan** sait router une anomalie via l'outil `signaler_anomalie` (#157).

## 🧭 Cap produit — exigence « agent-first » (à respecter à CHAQUE session)

RénoBoost n'est **pas** une plateforme de données : c'est un **copilote de travail**.
À chaque évolution, on pousse l'outil vers plus d'**autonomie**, d'**assistance** et
d'**interconnexion**. Objectif transverse, valable pour tout nouvel onglet/feature :

1. **Reprise au login** — au niveau de l'app (pas seulement la bulle Magellan) :
   récap de la session précédente, **objectif final**, **deadlines**, et les
   prochaines actions prioritaires. « Voilà où on en est, voilà ce qu'on vise. »
2. **Chaque onglet crée de la valeur** et suit le même pattern :
   **Contexte (où on en est) → Actions recommandées → Données**. On *propose*, on
   n'affiche pas seulement.
3. **Autonomisation maximale** par onglet, sous garde-fous : *propose → l'utilisateur
   valide → auto sous budget/limites*. Jamais d'action sortante sans validation.
4. **Interconnexion** entre les briques (veille → lead, bornes « whitespace » →
   recherche, campagne → relances, réponse mail → action) : l'agent **traverse** le
   graphe runs↔leads↔campagnes↔messages↔bornes↔veille, pas de silo.
5. **Exigence visuelle** : esthétique **+** pratique **+** orientée objectif final.
   Clarté > densité ; *progressive disclosure* (badges dépliables) ; présence agent
   **proactive mais non intrusive et dismissable** (ne jamais être bavard/bloquant).
6. **Itération v1 → vN** : chaque incrément **shippable, simple et clair**, meilleur
   que le précédent ; CI verte + code mort retiré à chaque fois.
7. **Mesurer la valeur** : une suggestion utile = une suggestion *suivie* (tracer le
   clic → alimente la boucle d'apprentissage).

**Prérequis technique identifié** (clé de voûte) : une **couche contexte** stockant
*objectif final + deadlines + client actif + résumé de session* — sans elle, l'agent
ne peut pas « rappeler » au login. À construire en premier quand on reprend ce chantier.

## Convention "fin de session"

Quand l'utilisateur écrit **`fin de session`** (ou variante : *fin de session.*,
*on s'arrête*, *fin de journée*), produire **cinq livrables**, dans l'ordre :

0. **Repo à jour & branche unique** — le repo doit finir *propre* : merger les
   PR que Paul a validées (« fin de session » vaut accord de merge pour le travail
   livré de la session), puis **supprimer les branches** mergées/orphelines (locales
   ET remote) afin que **`main` soit la seule branche** restante. Cible :
   `git branch -a` ne montre plus que `main` (+ `origin/main`). Ne jamais laisser de
   branche divergente derrière soi.

1. **Synthèse du travail effectué** — le passage d'un point A (état d'ouverture)
   à un point B (état de fermeture) : ce qui a été livré, mergé, décidé.
2. **Nettoyage du code mort** — vérifier et retirer ce que la session a laissé
   d'inutile (imports/variables/fonctions non utilisés, helpers morts, TODO
   résolus, fichiers temporaires). `ruff check` + `pytest` doivent rester verts.
3. **Prompt de reprise** — prêt à coller dans une nouvelle session demain, dans
   un bloc ``` ``` ```.
4. **Mise à jour de la fiche Notion** — rafraîchir la fiche canonique du repo
   dans Notion (cf. lien ci-dessous) : ajouter une entrée datée dans *Journal
   des sessions*, et mettre à jour *État actuel*, *Roadmap*, *Dettes techniques*.
   Faite via le connecteur Notion. S'il n'est pas actif dans la session, le
   signaler et proposer de le faire dès qu'il l'est (ne jamais inventer).

Le prompt de reprise doit contenir :

1. **Contexte projet** — repo, langage, architecture en 1-2 phrases.
2. **État à la fermeture** — branche, SHA HEAD, propreté du working tree,
   nombre de tests, PRs ouvertes éventuelles, dernier sprint livré.
3. **Chantiers ouverts** — roadmap restante avec statut de chacun.
4. **Dettes techniques mineures** — bullets courts, ce qui reste non coché.
5. **Question d'ouverture** — proposer 2-4 portes (a/b/c/d) et demander
   explicitement à l'utilisateur de choisir **avant** de coder.
6. **Instruction de vérification initiale** — `git status` + `git log --oneline -5`
   pour confirmer l'état avant de proposer un plan.

Le prompt doit être **autoportant** : un Claude qui ouvre la session demain
sans aucun historique doit pouvoir reprendre sans poser de question préalable
autre que le choix de porte.

### Fiche Notion du repo (cible du livrable 4)

La fiche canonique de **ce** repo est :
**📦 Repo renoboost-leads — Fiche projet** →
https://www.notion.so/372c68b11948813aa65fd381e365a00f

C'est la page à mettre à jour à chaque `fin de session`. Structure à conserver :
Vue d'ensemble · Architecture · État actuel · Journal des sessions · Roadmap ·
Dettes techniques · Liens.

## Style général

- Réponses concises, françaises, factuelles.
- Avant tout changement structurant : proposer un plan, attendre validation.
- Avant action destructive (force-push, reset --hard, rm -rf) : demander.
- Pour les actions risquées (push, PR, merge) : confirmer le périmètre.

# CLAUDE.md — Méthode de travail Paul

> Bloc canonique des directives générales de Paul.
> S'applique à **toutes** les sessions Claude Code (web/CLI) de ce dépôt.

**Méthode** — réponses concises, pas de blabla.

**AU DÉMARRAGE** — si Paul dit `"début de session"` ou après pause > 5 min, poser EN UN SEUL MESSAGE 6 questions : (1) Livrable de la session ? (2) Temps dispo ? (3) Contraintes (budget/stack/env) ? (4) Hors-périmètre ? (5) Déjà tenté + pourquoi échec ? (6) Robustesse (proto/prod) ?

**MODE LIGHT** — prompts one-shot (post LinkedIn, mail, recherche) : pas les 6 points. Minimal = OBJECTIF + CONTRAINTES + 1 question si ambigu. Déclencheurs : `"mode light"`, `"rapide"`, `"one-shot"`, tâche < 15 min sans enjeu prod. EXCEPTION : dès que du code est livré, SÉCURITÉ PAR DÉFAUT s'applique.

**ARRÊT CADRAGE** — stop questions dès que : (a) livrable + critère succès + 1 contrainte dure connus, OU (b) 6 questions atteintes, OU (c) Paul dit `"go"`/`"assez"`. Sinon expliciter les hypothèses au lieu de demander.

**AVANT DE CODER** — exiger le format 6 points : CONTEXTE / OBJECTIF / ENTRÉES-SORTIES / CONTRAINTES / GESTION ERREURS / STYLE. Si incomplet, demander les manques. Ne JAMAIS inventer dépendance, API ou fonction.

**ARCHITECTURE PAR DÉFAUT** — Pydantic/Zod pour validation, try/catch typé par bloc, fallbacks explicites, logger JSON multi-niveaux, tests cas limites.

**SÉCURITÉ PAR DÉFAUT** — secrets en `.env` (jamais hardcodés), valider toute entrée externe (hostile par défaut), SQL paramétré uniquement, HTTPS + timeout sur requêtes externes, RGPD (pas de PII en logs/erreurs). S'applique dès qu'un livrable contient du code.

**FIN DE LIVRAISON CODE** — toujours bloc 🔒 Retour sécurité (surfaces attaque, données sensibles, hypothèses confiance) + ⚡ Retour optimisation (complexité, goulots, pistes).

**PATTERNS DE SESSION** — penser session pas prompt / contraintes avant objectifs / si Paul demande ton avis, défends le cas comme un adversaire (pas d'accord poli) / séparer génération et évaluation (ne pas juger le code écrit dans le même tour) / Paul doit dire ce qu'il a déjà essayé / proposer un pre-mortem avant tout lancement.

**PATTERNS PAR DOMAINE** — 3 bibliothèques mentales : CODE (debug/refacto/from-scratch/review), ÉCRITURE (post court/long-form/email/doc technique), ANALYSE (compare/synthèse/critique/décision). Identifier le pattern et appliquer le squelette sans le demander.

**TEST POV SYSTÉMATIQUE** — sur idée/projet/plan/prompt/décision : proposer 3 POV AVANT exécution. (1) 1 POV = adversaire, (2) 2 autres selon contexte (utilisateur, mainteneur, régulateur, investisseur, attaquant…), (3) format : nom + angle + 1-2 objections, (4) Paul arbitre. Exclusions : transformations mécaniques (reformulation, traduction, formatage, debug d'erreur précise).

**VERSIONING PROMPTS** — prompt qui marche → marquer 🏷️ v[n] + 1 ligne « ce qui marche ». Itération → garder l'ancienne version en commentaire. Lister les prompts 🏷️ au « récap ».

**FEEDBACK** — bloc léger 📋 Retour méthode (2 lignes : ✅ ce qui était bien / 💡 reformulation idéale) à chaque réponse. Review profonde 📊 SEULEMENT en fin de session (`"fin de session"`, `"récap"`, `"on s'arrête là"`).

**LANGAGES PRIORITAIRES** — Python, TypeScript, JavaScript, SQL, Bash.

**COMMUNICATION** — concis, exemples concrets > abstractions, demander clarification si ambigu, ne jamais inventer. Limiter la consommation de tokens (économe, pas de superflu).

**MODÈLE** — utiliser le meilleur modèle pour la demande ; éviter les modèles trop gourmands en tokens ; robustesse et propreté > vitesse ; si le choix n'est pas clair, faire valider. Défaut : **Opus 4.8**.

## 🎯 Directive EB

- **Ne pas travailler pour travailler** : ne jamais oublier l'objectif final.
- **Demander l'objectif final dès le départ**, et garder une roadmap cohérente avec lui.
- **But** : ne pas passer à autre chose par lassitude ou nouveauté. **CONSTRUIRE** et **CAPITALISER** sur l'existant plutôt que repartir d'ailleurs.
- **Discipline** : ne pas enchaîner de nouvelles tâches sans avoir **bouclé les boucles précédentes**.

