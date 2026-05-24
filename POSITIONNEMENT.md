# POSITIONNEMENT — vision, moat, et ce qu'on emprunte au marché

Document de référence stratégique. À consulter pour toute décision qui
touche à l'identité du produit ou à l'opportunité d'ajouter une feature
vue ailleurs.

## 1. Vision

Une **plateforme de prospection commerciale pilotée par un agent IA**,
utilisable depuis le téléphone comme l'ordinateur, qui couvre toute la
chaîne dans un seul outil :

> trouver des prospects → identifier les entreprises → trouver les
> décideurs et leurs coordonnées → générer des mails personnalisés →
> valider → envoyer.

L'agent IA prend en charge la réflexion, affine les recherches, et
produit du résultat selon les critères de livrable du client.

## 2. Modèle économique cible (V1+)

**Location de l'outil** (SaaS) avec prise en main rapide et instantanée
par des clients professionnels. Chaque client ré-instancie l'outil pour
**sa** verticale (son offre commerciale). Modèle proche d'une marque
blanche / agence pivotable par verticale. Voir multi-tenant dans
`TODO_v1.md`.

## 3. Notre moat (ce que personne ne fait, à protéger absolument)

1. **Détection terrain physique** — partir d'une surface au sol
   (toiture, parking) détectée par satellite/cadastre → remonter au
   propriétaire → au décideur. Aucun AI SDR ne fait ça (ils partent
   tous de bases de contacts digitales). C'est notre vrai différenciant.
   Brique L0, V1.
2. **FR-natif + données publiques gratuites** — data.gouv.fr / SIREN,
   RGPD intérêt légitime B2B, langue française native. Les concurrents
   sont US/anglais et payants cher.
3. **Outil louable et pivotable par verticale** — modèle agence, pas
   mono-utilisateur.
4. **Humain dans la boucle au draft** — validation N2 obligatoire avant
   envoi. Assumé comme argument de vente, pas comme retard (cf section 5).

## 4. Le marché existant (état 2026)

La catégorie « AI SDR » (agent autonome qui trouve → enrichit →
personnalise → envoie → gère les réponses) existe et est encombrée,
surtout aux US :

| Outil | Reconnu pour |
|---|---|
| 11x.ai (Alice/Jordan) | SDR 100 % autonome, recherche→RDV |
| Artisan (Ava) | Base propriétaire 300 M+ contacts, 65 data points |
| AiSDR | Recherche temps réel "people with problems you can solve" |
| Clay | Orchestration data (le couteau suisse power-user) |
| Landbase / Agent Frank / Luru | SDR 24/7 multi-canal |

**Conclusion** : on n'invente pas la catégorie. Mais notre combinaison
exacte (détection terrain + FR-natif gratuit + pivotable/louable +
humain au draft) n'existe pas sur le marché.

## 5. Ce qu'on emprunte — patterns d'exécution, pas features

Distinction clé (validée avec l'utilisateur) : on s'inspire de **ce qui
fait leur vitesse d'exécution et leur réputation**, pas de leur liste de
features. Le projet reste différent d'eux.

### 5.1 Patterns d'exécution / UX à adopter (esprit, pas copie)

| Pattern | Ce qu'on en retient | Où |
|---|---|---|
| **Onboarding en minutes** | Le temps "zéro → première campagne" doit se compter en minutes. C'est ce qui les rend adoptables. → wizard chat agent ultra-court. | V0 (D3-D4) |
| **Vente sur signal** (signal-based selling) | Prioriser sur signaux observables, pas listes statiques. → nos `signaux:` pilotent explicitement le scoring L4. | V0 (D4) |
| **Qualification logic explicite** | Critères "bon lead" déclarés et visibles. → section `qualification:` du verticale.yaml. | V0 (D1/D4) |
| **Recherche/enrichissement en parallèle à l'échelle** | Traiter N leads de front, pas en série. → garder le pipeline parallélisable, cache agressif. | V0 (déjà partiel) |
| **Playbooks par cas d'usage** | Templates prêts par situation. → c'est exactement notre concept de verticale pré-câblée. | V0 |
| **Discipline de délivrabilité** | Warm-up, multi-expéditeur, vérif bounce comme citoyens de 1ère classe. | V0 (déjà PRE_MORTEM R5) |
| **Orchestration propre** (façon Clay) | Étages composables, sources pluggables. → notre dispatcher strategies/orchestrator par étage. | V0 (D1) |

### 5.2 Features à emprunter PLUS TARD (V1, parquées dans TODO_v1)

- Reply handling : l'agent drafte la réponse au prospect, l'humain
  valide (extension naturelle du staging N2).
- Signaux d'achat temps réel (levées, recrutement, news).
- Multi-canal LinkedIn + tél.
- Prise de RDV automatique (Calendly dispo dans l'environnement).
- Dashboard conversion / analytics.

### 5.3 Ce qu'on REJETTE (dénature le projet)

| Rejeté | Pourquoi |
|---|---|
| Construire une base propriétaire 300 M+ contacts | Conflit avec l'approche FR + sources gratuites. Au pire, source payante optionnelle plus tard. |
| Autonomie 100 % sans humain | Conflit frontal avec notre cœur "validation au draft". Et statistiquement moins performant (hybride > autonome 68,7 % du temps). |
| Positionnement US/anglais générique | Notre niche est FR-natif + verticales physiques. |

## 6. Règle d'arbitrage face à une idée "vue ailleurs"

Avant d'adopter quoi que ce soit vu chez un concurrent, passer le filtre :

1. **Est-ce gratuit ?** (recadrage d'une brique qu'on construit déjà) →
   éventuellement V0.
2. **Est-ce une feature nouvelle ?** → `TODO_v1.md`, point. Pas de débat
   avant le 1er juin.
3. **Est-ce que ça dénature le moat (section 3) ?** → rejet.

Rappel : ajouter des features ne fait jamais aller plus vite vers la V0.
Ça la retarde. On emprunte l'**esprit d'exécution**, pas la roadmap des
autres. Risque #1 du PRE_MORTEM = scope creep.
