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

## Cible V0 — 1er juin 2026 (freeze scope)

L'outil cesse d'être un outil de prospection solaire et devient une
**plateforme générique de prospection B2B pivotable par verticale**.
Le solaire devient une verticale parmi d'autres.

**Définition canonique « verticale »** : *offre commerciale d'un client
professionnel utilisateur de l'outil*. Pas un secteur cible. Une
verticale encapsule offre + cibles + zone-type + signaux + ton mail +
séquence. Voir [VERTICALES.md](./VERTICALES.md).

**Cible V0** : utile et exploitable en ligne le **lundi 1er juin 2026**.
Pas beau. L'esthétique = V1.

**Périmètre V0 figé** :
- Pipeline L1→L4 existant + agent IA copilote (déjà là)
- Objet `Verticale` 1ʳᵉ classe + dossier `verticales/`
- Agent discovery conversationnel (génère verticale depuis dialogue libre)
- Wizard Streamlit agent-driven (chemin nominal) + mode expert YAML
- Perso mail lead-par-lead (lecture site web + tone verticale)
- Vue mobile lisible (Streamlit responsive, pas PWA)
- 3 verticales d'exemple câblées + 1 run pilote réel
- B2B-only (B2C particulier → V1)

**Hors V0** : L0 détection terrain, carte des leads, dashboard ROI,
multi-tenant complet, LinkedIn multi-canal, signaux d'achat, PWA
installable, esthétique. Voir [ROADMAP_V0.md](./ROADMAP_V0.md).

**Règle scope creep** : toute demande hors V0 part dans `TODO_v1.md`
sans discussion. À rappeler à chaque tentation.

**Agent-first** : l'agent IA est le canal nominal d'interaction.
Streamlit affiche, l'agent pilote. Pas de site statique à formulaires.

**Pré-mortem** : 15 risques identifiés avec mitigations câblées. Voir
[PRE_MORTEM.md](./PRE_MORTEM.md). Risque #1 = scope creep.

**Méthode de progression** :
- Tests verts non négociables (617+ tests, on monte vers 650+)
- 1 PR draft par sprint (D1, D2, D3+D4, D5, D6, D7)
- 1 run réel quotidien à partir de D5
- Journal de session chaque soir (`data/agent/journal.md`)
- Réflexion 48-72h (22-24 mai) avant D1 (25 mai matin)

## Documents de cadrage V0 (à consulter en début de session)

- [ROADMAP_V0.md](./ROADMAP_V0.md) — rétro-planning jour par jour + prompt de kickoff D1
- [VERTICALES.md](./VERTICALES.md) — définition, schéma YAML, 3 verticales V0
- [PRE_MORTEM.md](./PRE_MORTEM.md) — risques + mitigations + règles dures
