# 00 — Cadrage Design · RénoBoost (interface commerciale partagée)

> **But du document** : poser le cadre *complet* du chantier design **avant** d'écrire
> la moindre ligne de style, pour qu'une session de design parte précise et cohérente
> avec l'existant. C'est la **boussole** : direction visuelle, identité, principes,
> périmètre, critères de réussite. Les specs détaillées vivent dans les fichiers `01`,
> `02` (écrans) et les prompts prêts à coller dans `03`.
>
> **Statut** : proposition à valider. Décisions de cadrage déjà prises avec Paul (cf. §3).

---

## 1. Contexte produit

RénoBoost-Leads est un **moteur** de prospection B2B (pipeline Python 5 étages → Supabase)
**+ une app web** (`web/`, Next.js 15) qui transforme ce moteur en **copilote commercial**
utilisable à deux. L'app existe déjà et tourne : 10 onglets, ~40 composants, 26 migrations.

Ce chantier **n'est pas une refonte fonctionnelle** : les écrans existent et marchent.
C'est un **chantier d'identité visuelle + design system** pour faire passer l'interface
d'« utilitaire qui marche » à « produit crédible en clientèle, agréable au quotidien ».

| Utilisateur | Rôle | Usage de l'interface |
|---|---|---|
| **Paul** | Admin / pilote | Cible, supervise, garde la main sur le moteur et l'agent |
| **Associé (commercial)** | Terrain | Traite les prospects, envoie, suit les réponses — y compris **sur mobile en clientèle** |

**Promesse** : *« Un copilote qui me dit où on en est, ce qu'on vise, et la prochaine
action — dans une interface que je n'ai pas honte de montrer à un prospect. »*

---

## 2. État des lieux visuel (audit de l'existant — point de départ obligé)

Le design actuel est **fait main** (pas de shadcn/ui), cohérent mais utilitaire. À **garder**
comme socle, à **faire évoluer** sans tout casser.

### Ce qui existe et qu'on garde (l'ADN)
- **Tokens CSS** dans `app/globals.css` : `--bg #f7f8fa` · `--card #fff` · `--border #e6e8ec`
  · `--text #11181c` · `--muted #687076` · `--brand #1f7a4d` (vert) · `--brand-dark #155c39`.
- **Carte canonique** : `rounded-xl border border-[var(--border)] bg-white`.
- **Titre de section** : `text-sm font-semibold uppercase tracking-wide text-[var(--muted)]`.
- **Pastilles de statut** lead (8) et run (4) : paires Tailwind `bg-X-100 text-X-800`
  (`lib/ui.ts` → `LEAD_STATUS_COLOR`, `RUN_STATUS_COLOR`). **Sémantique à préserver.**
- **Échelle de score** : `scoreColor()` (emerald ≥75 / amber ≥50 / slate) + `scoreVerdict()`
  (verdict commercial en toutes lettres). C'est une signature produit — on la systématise.
- **Pattern agent-first déjà codé** : `ActionsBand` (bandeau « 🧭 Où on en est — prochaines
  actions »), `RepriseBanner`, `WelcomeModal`, widget assistant, motif **🧭 Magellan**.
- **Sidebar** gauche compacte (icônes) qui se déplie au survol.

### Ce qui pèche (à corriger par le design system)
1. **Icônes = emojis** (`👥 📊 ✉️ 🔌 🎯 🤖 🔥 ☀️ ⏰`). Rendu incohérent multi-OS, peu pro
   en clientèle. → Migrer vers un jeu d'icônes vectoriel unifié (cf. `01`).
2. **Pas d'échelle typographique** : tailles ad hoc (`text-2xl`, `text-sm`…) sans rythme.
3. **Couleur d'accent unique** (un seul vert) : pas de nuancier, contrastes parfois justes,
   états hover/focus/disabled non standardisés.
4. **Pas de mode sombre** alors que les références (Linear, Vercel) en font un marqueur.
5. **Densité hétérogène** : padding/gaps variables d'un écran à l'autre.
6. **Composants dupliqués** : `Stat`, `FunnelBar`, `FilterChip` redéfinis localement page par
   page plutôt que partagés.

---

## 3. Décisions de cadrage (verrouillées avec Paul)

| Question | Décision |
|---|---|
| **Direction visuelle** | **Mix** des 4 références, **ancré dans l'existant** pour la cohérence (pas de table rase). |
| **Marque** | **Repartir sur « RénoBoost »** (aligner l'app sur la marque du projet ; abandonner « ReSign CRM »). |
| **Références-boussoles** | **Linear** (netteté, vitesse perçue, sobriété) · **Attio/Pipedrive** (CRM : pipeline, fiches riches, tables élégantes) · **Notion** (douceur, lisibilité, gris chauds) · **Stripe/Vercel** (dataviz soignée, sérieux tech premium, mode sombre). |
| **Périmètre 1ʳᵉ passe** | **Design system + 3 écrans clés** : Prospects (Inbox), Fiche lead, Tableau de bord. Le reste suivra. |

### Comment on fait « le mix » sans bouillie (clé de lecture)
On affecte **une référence par couche** pour que le mélange soit cohérent, pas aléatoire :

| Couche | Boussole dominante | Traduction concrète |
|---|---|---|
| **Squelette / densité / vitesse** | **Linear** | Grilles nettes, peu d'ombres, micro-transitions sobres, sidebar et raccourcis. |
| **Logique métier CRM** | **Attio / Pipedrive** | Fiche lead riche, pipeline lisible, tables triables, pastilles de statut. |
| **Ton / lisibilité / chaleur** | **Notion** | Gris légèrement chauds, generous line-height, langage humain, vide accueillant. |
| **Dataviz / crédibilité / sombre** | **Stripe / Vercel** | Tableau de bord soigné, nuancier d'accent maîtrisé, dark mode propre. |

---

## 4. Identité de marque — RénoBoost

> Piste à valider en ouverture de la session design. Volontairement **proche de l'existant**
> (le vert reste l'âme) mais structurée.

- **Nom d'app** : **RénoBoost** (sous-titre optionnel « Copilote commercial » ou « Pilote leads »).
  Remplace « ReSign CRM » dans la sidebar, le `<title>`, les e-mails, la doc.
- **Métaphore** : la **boussole 🧭 / Magellan** est déjà le motif de l'agent dans le code
  (« bulle Magellan », logo 🧭). On en fait le **fil conducteur de marque** : RénoBoost = le
  cap, l'agent Magellan = le navigateur. → un logo « boussole » vectoriel simple, vert.
- **Palette** (détaillée en `01`) : le **vert #1f7a4d devient `brand-600`** d'un nuancier
  complet (50→950). **Accent solaire** ambre/or (le ☀️ déjà présent pour le potentiel
  solaire) comme couleur secondaire de mise en avant. Neutres **légèrement chauds** (Notion).
- **Typo** : une **sans-serif géométrique lisible** (ex. *Inter* / *Geist*, déjà l'esprit
  Vercel) avec une échelle de tailles cadrée. Chiffres tabulaires pour la dataviz.
- **Ton éditorial** : français, direct, orienté action (déjà le cas dans `nextAction()`,
  `scoreVerdict()`). On propose, on ne se contente pas d'afficher.

---

## 5. Principes de conception (alignés sur la charte agent-first de `CLAUDE.md`)

1. **Contexte → Actions recommandées → Données**, sur **chaque** écran (déjà amorcé via
   `ActionsBand`/`RepriseBanner` ; on en fait un **invariant de layout**).
2. **Un écran = une tâche.** Divulgation progressive : le quotidien est trivial, l'avancé
   est replié (badges dépliables, zones « Avancé »).
3. **Présence agent proactive mais non intrusive et *dismissable*.** Jamais bavard, jamais
   bloquant.
4. **Clarté > densité**, mais **densité maîtrisée** où le métier l'exige (tables de leads).
5. **Mobile-first sur les parcours terrain** (Inbox, Fiche lead) ; desktop pour le pilotage.
6. **Cohérence avant nouveauté** : tout nouvel élément réutilise les tokens et composants du
   design system ; pas de one-off.
7. **Accessibilité** : contraste AA minimum, focus visible au clavier, cibles tactiles ≥ 44px,
   ne jamais coder une info par la seule couleur (statut = couleur **+** texte).

---

## 6. Périmètre de la 1ʳᵉ passe

### Inclus
- **Design system** complet et documenté (`01`) : tokens (couleurs/typo/espace/radius/ombres/
  motion), mode sombre, jeu d'icônes, **composants de base partagés** (Card, Stat, Badge de
  statut, Score, Button, FilterChip, Table, EmptyState, SectionTitle, ActionsBand revisité).
- **3 écrans clés re-stylés** (`02`) avec le nouveau système : **Prospects**, **Fiche lead**,
  **Tableau de bord**.
- **Rebrand léger** : nom RénoBoost + logo boussole + palette dans la sidebar et le login.

### Hors périmètre (passes ultérieures)
- Refonte des 7 autres onglets (Suivi, Campagnes, Bornes VE, Recherches, Cibles, Agent,
  Mode d'emploi) — ils héritent automatiquement des tokens, restylage fin plus tard.
- Changements fonctionnels / nouvelles features.
- Migration de stack (on **reste** Tailwind v4 fait-main ; introduction de shadcn/ui = décision
  séparée, cf. `01` §« option shadcn »).

---

## 7. Critères de réussite (definition of done)

- [ ] `globals.css` v2 : nuancier complet + tokens sémantiques + **dark mode**, sans régression
      visuelle sur les 7 écrans non retouchés (ils doivent rester corrects par héritage).
- [ ] Les 3 écrans clés appliquent le pattern **Contexte → Actions → Données** et le nouveau DS.
- [ ] **Zéro emoji décoratif** dans les 3 écrans clés (remplacés par icônes vectorielles) ;
      emojis tolérés ailleurs jusqu'à la passe suivante.
- [ ] Composants partagés extraits (plus de `Stat`/`FilterChip`/`FunnelBar` dupliqués).
- [ ] `npm run typecheck` + `npm run build` verts ; `next lint` propre.
- [ ] Contraste AA vérifié sur texte/statuts ; focus clavier visible partout.
- [ ] Rendu mobile correct sur Inbox + Fiche lead (testé largeur 375px).
- [ ] Capture avant/après des 3 écrans dans la PR.

---

## 8. Plan de construction (jalons vérifiables, dans l'esprit v1→vN de CLAUDE.md)

| Jalon | Contenu | Sortie vérifiable |
|---|---|---|
| **D0** | Valider ce cadrage + l'identité §4 (nom, logo, palette). | Feu vert écrit |
| **D1** | `globals.css` v2 (tokens + dark) + jeu d'icônes + 6 composants de base. Aucun écran retouché. | Build vert, écrans existants intacts |
| **D2** | Re-style **Prospects** (Inbox) avec le DS. | Avant/après, parcours OK |
| **D3** | Re-style **Fiche lead**. | Avant/après, parcours OK |
| **D4** | Re-style **Tableau de bord** (focus dataviz). | Avant/après, dark mode OK |
| **D5** | Rebrand sidebar + login (RénoBoost + boussole), polish mobile, doc 1 page. | Prod déployée |

Chaque jalon est **shippable** (PR draft, CI verte, code mort retiré) — un incrément meilleur
que le précédent.

---

## 9. Risques & décisions ouvertes (à trancher en ouverture de session)

1. **Police web** : *Inter* (neutre, sûre) vs *Geist* (signature Vercel) vs system-font (zéro
   coût réseau). → défaut proposé : **Geist via `next/font`**, fallback system.
2. **Mode sombre** : par défaut clair, sombre opt-in (toggle dans Compte) ? ou auto `prefers-
   color-scheme` ? → défaut proposé : **toggle + respect système au 1er chargement**.
3. **shadcn/ui** : l'introduire maintenant (gain : Dialog/Dropdown/Toast accessibles) ou rester
   fait-main ? → défaut proposé : **rester fait-main pour cette passe**, réévaluer ensuite.
4. **Accent solaire** : ambre comme 2ᵉ couleur de marque, ou la garder strictement sémantique
   (potentiel solaire) pour ne pas brouiller le message ? → défaut proposé : **sémantique +
   accent CTA secondaire discret**.
5. **Profondeur du rebrand** : juste le nom/logo, ou aussi les e-mails Instantly et la doc ? →
   cette passe : **app uniquement** ; e-mails/doc en D5 si le temps le permet.

---

## 10. Liens internes

- `01_DESIGN_SYSTEM.md` — tokens, dark mode, icônes, composants (avec `globals.css` v2 proposé).
- `02_ECRANS_CIBLES.md` — specs détaillées des 3 écrans (anatomie, états, responsive, recette).
- `03_PROMPTS.md` — prompts prêts à coller pour lancer chaque session de design.
