# CLAUDE.md — consignes session Claude Code

## Convention "fin de session"

Quand l'utilisateur écrit **`fin de session`** (ou variante : *fin de session.*,
*on s'arrête*, *fin de journée*), produire un **prompt de reprise prêt à coller
dans une nouvelle session demain**, dans un bloc ``` ``` ```.

Le prompt doit contenir :

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

## Style général

- Réponses concises, françaises, factuelles.
- Avant tout changement structurant : proposer un plan, attendre validation.
- Avant action destructive (force-push, reset --hard, rm -rf) : demander.
- Pour les actions risquées (push, PR, merge) : confirmer le périmètre.
