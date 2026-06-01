# CLAUDE.md — consignes session Claude Code

## Convention "fin de session"

Quand l'utilisateur écrit **`fin de session`** (ou variante : *fin de session.*,
*on s'arrête*, *fin de journée*), produire **quatre livrables**, dans l'ordre :

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
