# CLAUDE.md — consignes session Claude Code

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
