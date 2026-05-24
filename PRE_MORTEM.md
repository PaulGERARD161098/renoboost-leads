# PRE_MORTEM — pourquoi V0 pourrait échouer et comment l'éviter

Document de référence des risques V0 (cible 1er juin 2026). À consulter
au début de chaque sprint et en cas de tentation de scope creep.

## Méthode

15 risques identifiés en session du 21 mai 2026. Chaque risque a :
- **Probabilité** × **Impact** (qualitatif)
- **Mitigation** câblée dans le code ou dans le process
- **Signal d'alerte** : ce qui doit déclencher une revue

## Règles dures non négociables

1. **Tests verts à chaque fin de journée.** Si rouge le soir, on ne
   push pas. Première tâche du lendemain = fixer les tests.
2. **Scope creep interdit jusqu'au 1er juin.** Toute demande hors V0 va
   dans `TODO_v1.md` sans discussion. Aucune exception.
3. **1 PR draft par sprint.** Visibilité continue de l'avancement.
4. **1 run réel quotidien à partir de D5.** Sinon on code dans le vide.
5. **Journal de session chaque soir** dans `data/agent/journal.md` —
   3 lignes : marche / coince / lendemain.
6. **Pas d'envoi cold mail sans validation humaine item par item.**
   Mécanique staging Instantly N2 déjà en place — on ne la contourne pas.
7. **Cap budget API €/jour respecté.** Garde-fou `budget_eur_par_jour`
   déjà présent — on n'y touche pas à la baisse pour aller plus vite.

## Les 15 risques

### R1 — Scope creep [Très Haut × Très Haut]

**Description** : pendant 7 jours de code intensif, 20 idées vont
émerger (« et si on ajoutait LinkedIn… », « il faudrait une carte »).
C'est la cause #1 d'échec.

**Mitigation** :
- Périmètre V0 figé dans `CLAUDE.md` section freeze
- Toute idée nouvelle → `TODO_v1.md` immédiatement, sans débat
- Claude doit rappeler la règle à chaque tentation

**Signal d'alerte** : tu demandes ou je propose une feature qui n'est
pas dans le tableau in/out de `ROADMAP_V0.md`.

### R2 — Agent discovery génère YAML bancal [Haut × Haut]

**Description** : la génération de verticale depuis dialogue libre
(D2) est l'élément le plus innovant et le plus risqué. Si l'agent
produit des `verticale.yaml` invalides ou inutilisables, le wizard
agent-driven est cassé et la prise en main lambda est compromise.

**Mitigation** :
- 3 tests de génération sur 3 briefs typés (solaire, IRVE, ombrières)
- Validation schéma JSON Schema avant écriture disque
- L'agent affiche le YAML avant lancement, l'utilisateur amende
- Mode expert YAML reste accessible en parallèle (rail de secours)

**Signal d'alerte** : sur 5 briefs de test, > 1 verticale invalide.

### R3 — Mails génériques, taux de réponse < 2 % [Haut × Haut]

**Description** : sans perso lead-par-lead, les cold mails sonnent
robotiques. Bounce + spam. Domaine grillé en 48h.

**Mitigation** :
- D4 dédié à la perso : l'agent lit le site web du lead + tone de la
  verticale + signal individuel injecté dans le pitch L4
- Validation humaine du staging N2 obligatoire
- Pas plus de 30 mails/jour sur un domaine froid pendant warm-up
- NeverBounce avant Instantly (vérif batch)

**Signal d'alerte** : sur les 10 premiers mails du run pilote, > 3 ont
l'air interchangeables si on remplace le nom.

### R4 — L3 taux email trouvé trop bas [Haut × Moyen]

**Description** : sur scraping gratuit, 50-65 % de match email selon
verticale. Sur certaines verticales (artisans, indépendants), ça peut
tomber à 30 %. Sans email, pas de campagne.

**Mitigation** :
- Afficher honnêtement le taux de match dans le dashboard de session
- Activable Dropcontact L3.5 en 1 clic (payant, 0,15 €/lead)
- Wizard demande explicitement « tu acceptes de payer ~0,15 €/lead pour
  email vérifié ? » selon volume

**Signal d'alerte** : run pilote D5 avec < 40 % d'email trouvé.

### R5 — Cold mail FR sans warm-up [Haut × Haut]

**Description** : envoyer depuis un domaine froid sans warm-up Instantly
= domaine sur liste de blocage en 48h. Tout le pipeline derrière devient
inutilisable.

**Mitigation** :
- Wizard demande explicitement le statut warm-up du domaine
- Refuser le lancement si > 30 mails/jour sur domaine non warmé
- Recommander domaine sacrifiable (pas le domaine pro principal)
- Instantly fait le warm-up natif — utiliser

**Signal d'alerte** : utilisateur saute la question warm-up dans le wizard.

### R6 — API quotas / coûts dérapent [Moyen × Haut]

**Description** : Google Places facture au-delà du quota gratuit.
Anthropic facture à l'usage. Sur un run de 500 leads avec Sonnet, on
peut atteindre 50 €.

**Mitigation** :
- Cap budget `budget_eur_par_jour` (déjà existant — défaut 5 €)
- Estimation pré-run dans le wizard : montrer le coût avant lancement
- Refuser run si budget restant insuffisant

**Signal d'alerte** : run qui rejette pour dépassement budget.

### R7 — Streamlit Cloud limites free tier [Moyen × Moyen]

**Description** : free tier 1 GB RAM, app dort après 7j inactivité.
Sur des sessions lourdes (500 leads + L4), risque OOM ou timeout.

**Mitigation** :
- Surveiller mémoire en D5-D7
- Si limite atteinte → upgrade plan payant (~20 €/mois)
- Persistance Supabase déjà en place — pas de perte de données si app
  redémarre

**Signal d'alerte** : crash Streamlit en D5 ou D6.

### R8 — Quality data.gouv.fr [Moyen × Moyen]

**Description** : SIREN match 70-85 %, certains secteurs (artisans
locaux) pires.

**Mitigation** :
- Afficher taux match dans dashboard session
- Permettre re-run L2 avec stratégie alternative (recherche par nom +
  ville si SIREN par adresse échoue)
- Documenter limites par verticale

**Signal d'alerte** : taux match < 60 % sur une verticale.

### R9 — RGPD FR cold mail B2B [Moyen × Haut]

**Description** : intérêt légitime B2B accepté en France mais exige
mentions + opt-out + registre. Manquement = CNIL.

**Mitigation** :
- Registre RGPD par session déjà en place (`registre_rgpd.md`)
- Vérifier que chaque mail contient lien désabo + mentions légales
- Commande `forget` existante pour droit à l'oubli
- Pas de B2C en V0 (consentement explicite requis, plus complexe)

**Signal d'alerte** : mail de test envoyé sans lien désabo.

### R10 — Tests cassent en cours de route [Moyen × Moyen]

**Description** : 617 tests à maintenir verts pendant 7 jours de
modifications structurelles (objet Verticale, dossier verticales/, agent
discovery).

**Mitigation** :
- Règle dure : tests verts en fin de journée
- Pre-commit déjà configuré
- 1 PR par sprint → CI fait le check à chaque push

**Signal d'alerte** : > 1 sprint qui pousse avec tests rouges.

### R11 — Burnout 7j d'affilée [Moyen × Moyen]

**Description** : 50-65 h de code sur 7 jours = intense.

**Mitigation** :
- Weekend 30-31 mai planifié comme jours plus légers (runs + fix
  uniquement, pas de nouveau code)
- Réflexion 48-72h avant D1 (22-24 mai) — pas de précipitation
- Buffer D7 (dimanche) absorbe les retards

**Signal d'alerte** : 2 jours consécutifs > 8 h de code intense.

### R12 — Run réel D5 ne donne pas de leads exploitables [Moyen × Haut]

**Description** : le pilote D5 peut révéler que la verticale choisie
ne produit pas de leads qualifiés (taux match bas, signaux absents,
templates inadéquats).

**Mitigation** :
- D5 est justement le moment de découvrir ça, pas D-day
- D6 prévu pour pivot ciblé si D5 échoue
- 3 verticales V0 = 3 chances

**Signal d'alerte** : verticale #1 produit < 10 leads top en D5.

### R13 — Instantly indisponible / changement API [Faible × Moyen]

**Description** : dépendance externe pour le cold mailing.

**Mitigation** :
- Mode dry-run existe déjà
- Fallback : export CSV qualifié vers Lemlist / Smartlead / manuel

**Signal d'alerte** : `INSTANTLY_DRY_RUN=true` forcé par erreur API.

### R14 — Wizard sous-spécifié (5 questions ne suffisent pas) [Faible-Moyen × Moyen]

**Description** : certaines verticales demandent 15 paramètres précis.
Le wizard chat peut underfit.

**Mitigation** :
- Conversation libre (pas 5 questions fixes) — l'agent peut poser des
  follow-ups dynamiques
- Mode expert YAML reste accessible
- L'utilisateur peut amender la verticale après génération

**Signal d'alerte** : utilisateur revient au YAML brut systématiquement.

### R15 — Utilisateur lambda ne sait pas répondre aux questions [Faible × Haut]

**Description** : un utilisateur non-tech peut être bloqué par
« quels codes NAF ? », « rayon en km ? ».

**Mitigation** :
- L'agent reformule en langage naturel : pas de NAF demandé, on demande
  « quel type d'entreprise tu vises ? »
- Défauts sensés pour les paramètres techniques
- Exemples concrets dans chaque question

**Signal d'alerte** : utilisateur abandonne le wizard à mi-parcours.

## Tableau récapitulatif

| # | Risque | P | I | Mitigation principale |
|---|---|---|---|---|
| 1 | Scope creep | TH | TH | TODO_v1.md systématique |
| 2 | Agent génère YAML bancal | H | H | 3 tests typés + validation schéma |
| 3 | Mails génériques | H | H | Perso lead-par-lead D4 |
| 4 | L3 emails trop bas | H | M | Dropcontact en 1 clic |
| 5 | Cold mail sans warm-up | H | H | Refus lancement > 30 mails/j |
| 6 | API coûts dérapent | M | H | Estimation pré-run + cap budget |
| 7 | Streamlit Cloud limites | M | M | Upgrade plan si besoin |
| 8 | data.gouv.fr quality | M | M | Afficher taux + stratégie fallback |
| 9 | RGPD FR | M | H | Registre + opt-out vérifiés |
| 10 | Tests cassent | M | M | Verts en fin de journée non négociable |
| 11 | Burnout | M | M | Weekend léger + buffer D7 |
| 12 | Run pilote sans leads | M | H | 3 verticales = 3 chances |
| 13 | Instantly down | F | M | Mode dry-run + export CSV |
| 14 | Wizard sous-spécifié | F-M | M | Conversation libre + mode expert |
| 15 | Utilisateur bloqué | F | H | Reformulation langage naturel par agent |

# Partie II — Pré-mortem produit & passage SaaS (long terme)

Les 15 risques ci-dessus concernent **la livraison V0 du 1er juin**.
Cette partie concerne **la survie du produit au-delà**, en particulier
au moment du passage au modèle de location (SaaS multi-client). Aucun
de ces risques ne se matérialise en V0 (un seul opérateur, un domaine,
des runs maîtrisés) — ils se déclenchent **quand tu loues l'outil**.

Analyse fondée sur lecture du code réel (settings, scraper, budget,
storage Supabase, auth Streamlit, runner agent) en mai 2026.

## Constat de départ : le code est sain, l'architecture est mono-tenant

Points forts vérifiés dans le code (à ne pas casser) :
- Secrets en `SecretStr`, validation Pydantic stricte au démarrage
- Auth Streamlit en comparaison constant-time (`hmac.compare_digest`)
- Scraper politesse-first : respecte robots.txt, rate limit 1 req/s,
  User-Agent honnête, taille de réponse plafonnée
- Protection path-traversal sur tarballs (CVE-2007-4559 + symlinks)
- Dry-run par défaut sur Instantly, cap budget €/jour persistant
- 617 tests verts

Le code ne tuera pas le projet. Ce qui peut le tuer = l'écart entre
l'architecture **mono-utilisateur actuelle** et l'ambition **SaaS
multi-client**, plus la fragilité de la **délivrabilité**.

## Les 3 morts les plus probables du projet

### MORT-1 — La location tue le produit avant le décollage [structurel]

Tu loues à plusieurs clients sur une architecture mono-tenant :
- **Pas d'isolation des données** : `data/output/` partagé, un seul
  bucket Supabase, un seul `APP_PASSWORD`. Client A peut voir les leads
  de client B.
- **Pas d'attribution ni de plafond de coût par client** : le cap budget
  est global (`budget.json`), pas par tenant. Un client qui lance « toute
  la France » brûle TES clés Google/Anthropic/Dropcontact sans limite.
- **Pas de gestion d'utilisateurs** : un mot de passe unique, pas de
  révocation individuelle.
- **Responsabilité RGPD démultipliée** : tu deviens sous-traitant voire
  responsable conjoint (art. 28 RGPD), pour des pratiques de prospection
  que tu ne contrôles pas, multiplié par le nombre de clients.

**Conséquence** : fuite de données entre clients + coûts incontrôlés +
exposition juridique.

**Prérequis non négociable** : le **multi-tenant n'est pas une feature
V1 parmi d'autres, c'est LE prérequis du modèle économique**. Avant de
louer à un seul client externe, il faut :
1. Isolation stricte des données par tenant (bucket/préfixe ou projet
   Supabase par client, RLS activée)
2. Métering + cap de coût API **par tenant et par campagne**
3. Gestion d'utilisateurs réelle (comptes, rôles, révocation) — remplacer
   `APP_PASSWORD` unique
4. Cadre RGPD : contrat de sous-traitance type, registre par client,
   clause sur la légitimité des cibles du client

### MORT-2 — La délivrabilité s'effondre [opérationnel]

Toute la chaîne de valeur finit en cold mail. Emails scrapés de qualité
moyenne (L3 = 50-65 %) → bounce > 15 % → **domaines grillés** → zéro
réponse → les clients résilient.

**Prérequis** : la discipline de délivrabilité doit devenir un **citoyen
de première classe**, pas une note de bas de page :
1. Vérification batch obligatoire avant envoi (NeverBounce/ZeroBounce),
   bloquante si bounce estimé > seuil
2. Warm-up de domaine géré et imposé (refus d'envoi sur domaine froid
   au-delà d'un quota)
3. Cap d'envoi quotidien par domaine, par client
4. Séparation domaine de prospection / domaine pro principal

### MORT-3 — « Tout le monde peut l'utiliser » s'avère faux [adoption]

La thèse de location repose entièrement sur l'agent discovery (D2). S'il
génère des verticales bancales ou pose des questions trop techniques,
l'outil reste pilotable par l'expert (toi) seul → impossible à louer.

**Prérequis** : D2 est le sprint **le plus risqué et le plus
déterminant**. Critère de succès dur : un utilisateur non-technique crée
une verticale exploitable en conversation, sans jamais voir un code NAF
ni un YAML. Si ce critère n'est pas tenu, la thèse SaaS vacille — à
réévaluer avant d'investir dans le multi-tenant.

## Risques produit secondaires (à garder en tête, non bloquants V0)

| Axe | Risque | Quand ça mord |
|---|---|---|
| **Coûts** | Agent tourne sur Sonnet par défaut (6× Haiku) ; grille README chiffrée sur Haiku → coût réel sous-estimé | Dès les premiers runs agent-pilotés |
| **Coûts** | Pas de cap par campagne, seulement par jour | Run large multi-verticale |
| **Légal** | Cache Places persistant (SQLite + Supabase) potentiellement contraire aux ToS Google Places en usage commercial | Au passage commercial |
| **Sécurité** | Blast radius `service_role` key : si elle fuite, tout le bucket (toutes sessions, tous clients) exposé | Fuite secret / dépendance compromise |
| **Sécurité** | Autonomie agent N3 « boucle fermée » : dépense + agit sans validation | Si on monte le niveau d'autonomie |
| **Dépendances** | 6 fournisseurs externes hors contrôle (Google, data.gouv, Instantly, Anthropic, Supabase, Streamlit Cloud) ; un changement de ToS casse un étage | Imprévisible |
| **Données** | Qualité très variable par verticale (artisans/indépendants = match bas) ; une verticale peut « ne pas marcher » | Client loué déçu |
| **UX** | Streamlit responsive ≠ vraie ergonomie mobile | Adoption grand public |

## Règle d'or issue de ce pré-mortem

**Le passage à la location ne doit jamais être traité comme « ajouter des
comptes utilisateurs ».** C'est une refonte d'isolation + métering +
conformité. À planifier comme un chantier dédié post-V0, avec ses propres
critères d'acceptation, avant tout client externe payant.

# Revue de ce document

À ouvrir :
- À chaque début de sprint (D1, D2, D3, etc.)
- Avant chaque PR draft
- Lors de toute proposition de feature hors V0
- **Avant tout engagement de location à un client externe** (relire
  Partie II)

À mettre à jour :
- Si un risque se réalise (passer la mitigation en « post-mortem »)
- Si un nouveau risque émerge en cours de route

La Partie I (15 risques V0) est figée jusqu'au 1er juin sauf
matérialisation d'un risque nouveau majeur. La Partie II (produit/SaaS)
sera reprise et détaillée au moment de planifier le multi-tenant.
