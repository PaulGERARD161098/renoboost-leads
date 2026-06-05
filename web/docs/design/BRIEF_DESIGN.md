# Brief Design RénoBoost — fichier unique pour Claude

> **À coller tel quel dans une session Claude pour piloter le chantier design.** Autoportant :
> tout le contexte, les décisions, le design system et les 3 écrans cibles sont ici. Aucun
> autre fichier requis. Travaille sur la branche `claude/magical-johnson-WWWgz`, propose un
> plan avant tout changement structurant, jamais d'action sortante sans validation.

---

## 0. Mission

Faire passer l'interface commerciale de **RénoBoost-Leads** (app web `web/`, partagée entre
**Paul** = admin et son **associé commercial** = terrain/mobile) d'« utilitaire qui marche » à
**« produit crédible en clientèle, agréable au quotidien »**. Ce n'est **pas** une refonte
fonctionnelle : les écrans existent et marchent. C'est un chantier **identité visuelle +
design system + restyle de 3 écrans clés**.

**Stack** : Next.js 15 (App Router, RSC), React 19, **Tailwind v4 fait-main** (pas de
shadcn/ui), Supabase, déploiement Vercel. L'app vit dans `web/`.

---

## 1. Décisions verrouillées (ne pas rediscuter)

- **Marque** : repartir sur **« RénoBoost »** (abandon de « ReSign CRM »). Métaphore
  **boussole 🧭 / Magellan** (déjà le motif de l'agent dans le code) comme fil conducteur →
  logo boussole vectoriel vert.
- **Direction visuelle** : **mix** de 4 références, **ancré dans l'existant** (pas de table
  rase). Une référence par couche pour que le mix soit cohérent :
  - **Linear** → squelette, densité, vitesse perçue, sobriété, micro-transitions.
  - **Attio / Pipedrive** → logique CRM : fiche riche, pipeline lisible, tables triables.
  - **Notion** → ton, lisibilité, gris légèrement chauds, vide accueillant, langage humain.
  - **Stripe / Vercel** → dataviz soignée, nuancier maîtrisé, **dark mode** premium.
- **Périmètre 1ʳᵉ passe** : **design system + 3 écrans clés** (Prospects, Fiche lead, Tableau
  de bord). Les 7 autres onglets héritent des tokens et seront restylés plus tard.

---

## 2. Existant à préserver (l'ADN — point de départ obligé)

À **garder** comme socle, faire évoluer **sans casser** :

- **Tokens CSS** (`app/globals.css`) : `--bg #f7f8fa` · `--card #fff` · `--border #e6e8ec` ·
  `--text #11181c` · `--muted #687076` · `--brand #1f7a4d` (vert) · `--brand-dark #155c39`.
- **Carte canonique** : `rounded-xl border border-[var(--border)] bg-white`.
- **Titre de section** : `text-sm font-semibold uppercase tracking-wide text-[var(--muted)]`.
- **Sémantique statut/score** (`lib/ui.ts`) — **à préserver telle quelle** :
  - 8 statuts lead : `nouveau` slate · `a_valider` amber · `valide` blue · `envoye` indigo ·
    `ouvert` violet · `repondu` emerald · `a_relancer` orange · `ecarte` slate (paires
    `bg-X-100 text-X-800`).
  - Score : emerald ≥75 / amber ≥50 / slate sinon ; + `scoreVerdict()` (verdict commercial en
    toutes lettres) ; + `scoreGlobal()` (60 % commercial / 40 % foncier solaire).
- **Pattern agent-first déjà codé** (à généraliser comme invariant de layout) :
  `ActionsBand` (« 🧭 Où on en est — prochaines actions »), `RepriseBanner` (reprise au login),
  `WelcomeModal`, widget assistant.
- **Sidebar** gauche compacte (icônes) qui se déplie au survol.

**Ce qui pèche, à corriger par le design system** :
1. Icônes = **emojis** (rendu incohérent, peu pro) → jeu vectoriel unifié.
2. Pas d'échelle typographique (tailles ad hoc).
3. Couleur d'accent unique (un seul vert, pas de nuancier ; hover/focus/disabled non
   standardisés).
4. Pas de **mode sombre**.
5. Densité hétérogène d'un écran à l'autre.
6. Composants **dupliqués** (`Stat`, `FunnelBar`, `FilterChip` redéfinis dans chaque page).

---

## 3. Principes de conception (charte agent-first du projet)

1. **Contexte → Actions recommandées → Données** sur **chaque** écran (ordre vertical).
2. **Un écran = une tâche** ; divulgation progressive (l'avancé est replié).
3. Présence agent **proactive mais non intrusive et dismissable**.
4. **Clarté > densité**, densité maîtrisée où le métier l'exige (tables de leads).
5. **Mobile-first** sur les parcours terrain (Inbox, Fiche lead).
6. **Cohérence avant nouveauté** : tout réutilise tokens + composants ; pas de one-off.
7. **Accessibilité** : contraste AA, focus visible clavier, cibles tactiles ≥ 44px, statut =
   couleur **+** texte (jamais couleur seule).

---

## 4. Design system à produire

### 4.1 Couleurs
- **Marque** : le `#1f7a4d` devient **`brand-600`** d'un nuancier 50→950 :
  `50 #ecf6f0 · 100 #d3eadd · 200 #a8d6bd · 300 #74bd97 · 400 #3f9e6f · 500 #27885a ·
  600 #1f7a4d · 700 #176040 · 800 #155c39 · 900 #0f4b2e · 950 #08301d`.
- **Accent solaire** (ambre, parcimonieux — potentiel solaire / CTA secondaire) :
  `solar-400 #f5b740 · 500 #e29a17 · 600 #c27c0a`.
- **Neutres légèrement chauds** : `bg #f7f8fa · bg-subtle #eef0f3 · card #fff · border #e6e8ec
  · border-strong #d3d6db · text #11181c · text-muted #687076 · text-subtle #9aa0a6`.
- **Dark mode** : `bg #0b0d0f · bg-subtle #14171a · card #16191d · border #262b30 ·
  text #e8eaed · text-muted #9aa0a6` ; brand actif → `brand-500`.

### 4.2 `globals.css` v2 (Tailwind v4 — conserver les alias historiques)
```css
@import "tailwindcss";

@theme {
  --color-brand-50:#ecf6f0; --color-brand-100:#d3eadd; --color-brand-200:#a8d6bd;
  --color-brand-300:#74bd97; --color-brand-400:#3f9e6f; --color-brand-500:#27885a;
  --color-brand-600:#1f7a4d; --color-brand-700:#176040; --color-brand-800:#155c39;
  --color-brand-900:#0f4b2e; --color-brand-950:#08301d;
  --color-solar-400:#f5b740; --color-solar-500:#e29a17; --color-solar-600:#c27c0a;
  --radius-sm:8px; --radius-md:12px; --radius-lg:16px;
  --font-sans: var(--font-geist), -apple-system, "Segoe UI", Roboto, sans-serif;
}
:root {
  --bg:#f7f8fa; --bg-subtle:#eef0f3; --card:#fff; --border:#e6e8ec; --border-strong:#d3d6db;
  --text:#11181c; --muted:#687076; --text-subtle:#9aa0a6;
  --brand:var(--color-brand-600); --brand-dark:var(--color-brand-800);
  --brand-contrast:#fff; --ring:var(--color-brand-500);
}
.dark {
  --bg:#0b0d0f; --bg-subtle:#14171a; --card:#16191d; --border:#262b30; --border-strong:#333a41;
  --text:#e8eaed; --muted:#9aa0a6; --text-subtle:#6b7177;
  --brand:var(--color-brand-500); --brand-dark:var(--color-brand-700);
  --brand-contrast:#07130c; --ring:var(--color-brand-400);
}
html, body { background:var(--bg); color:var(--text); -webkit-font-smoothing:antialiased;
  font-feature-settings:"tnum" 1; }
* { box-sizing:border-box; }
:focus-visible { outline:2px solid var(--ring); outline-offset:2px; }
@media (prefers-reduced-motion: reduce) {
  * { transition-duration:.01ms!important; animation-duration:.01ms!important; }
}
```
> Garder les classes statut de `lib/ui.ts` telles quelles pour cette passe (zéro risque) ;
> juste revérifier leurs contrastes en dark.

### 4.3 Typographie
**Geist** via `next/font` (fallback system), chiffres **tabulaires** pour la dataviz. Échelle :
`display 30/36 bold · h1 24/32 bold · h2 18/28 semibold · eyebrow 12/16 semibold uppercase ·
body 14/20 · body-lg 16/24 · caption 12/16 · mono 13/20`.

### 4.4 Espacement / rayons / ombres / motion
- Échelle 4-pt (`4 8 12 16 24 32 48`) ; padding carte = 16, dense = 12 ; gap grille 16/24.
- Rayons : `sm 8 · md 12 (=rounded-xl) · lg 16 (=rounded-2xl) · full`.
- Ombres discrètes (Linear) : `sm` hover · `md` popover/sidebar · `lg` modale.
- Transitions 150ms ease-out (couleur/hover), 200ms (sidebar). `prefers-reduced-motion` OK.

### 4.5 Icônes — sortir des emojis (recommandé : `lucide-react`)
🧭→`Compass`(logo) · 👥→`Users` · 📊→`BarChart3` · ✉️→`Mail` · 🔌→`Plug` · 🔎→`Search` ·
🎯→`Target` · 📈→`LineChart` · 🤖→`Bot` · 📖→`BookOpen` · ⚙️→`Settings` · 🔥→`Flame` ·
☀️→`Sun` · ⏰→`Clock` · 🔔→`Bell` · 🔄→`RefreshCw`(animé) · ⏻→`LogOut` · ★→`Star`.
(Le ☀️ « potentiel solaire » peut rester comme marqueur métier si pertinent.)

### 4.6 Composants partagés à extraire dans `web/components/ui/`
`Card`/`CardHeader` · `SectionTitle(icon,count,action)` · `StatusBadge(status)` ·
`ScoreBadge(score, variant: commercial|solaire|global, size)` · `Stat(label,value,icon,trend)` ·
`Button(variant: primary|secondary|ghost|danger, size)` · `FilterChip(active)` · `DataTable` ·
`EmptyState(icon,title,cta)` · `ProgressBar(value,tone)` · `ActionsBand` (re-skin).
> Règle : on n'extrait un composant que s'il sert ≥2 fois. Pas de sur-abstraction.

### 4.7 Décisions ouvertes (proposer un défaut puis attendre la validation de Paul)
1. Police : **Geist** (défaut) vs Inter vs system. 2. Dark mode : **toggle + respect système**
au 1er chargement (défaut). 3. shadcn/ui : **rester fait-main** cette passe (défaut).
4. Accent solaire : **sémantique + CTA secondaire discret** (défaut). 5. Rebrand : **app
uniquement** cette passe (défaut).

---

## 5. Les 3 écrans clés (restyle, pas de changement métier)

### A. Prospects / Inbox — `app/(app)/inbox/page.tsx` (+ `actions-band`, `run-group`, `leads-table`)
Écran principal de l'associé : file de prospects, vue groupée par recherche (défaut) ou à plat.
- **Contexte** : carte « run en cours » avec `ProgressBar` + `RefreshCw` animé.
- **Actions** : `ActionsBand` re-skin (Réponses à traiter / Leads à valider / Relances dues /
  Appels à passer / Signaux de veille ; ★ = action apprise).
- **Données** : groupes dépliables (`RunGroup` : nom cible + zone + compteurs total/top≥75/
  hors-filtre) ou `DataTable` (Entreprise · Ville · `ScoreBadge` · `StatusBadge`).
- `FilterChip` partagés. **Mobile** : table → liste de cartes (tap = fiche, cibles ≥44px).
- États : vide (`EmptyState`→lancer recherche), erreur, **skeleton** de chargement.

### B. Fiche lead — `app/(app)/leads/[id]/page.tsx` (+ panels lead-*)
L'associé y passe 90 % du temps.
- **Hero score** : `ScoreBadge size=lg` (80×80) + verdict commercial + `ProgressBar` + ligne
  « global / commercial / ☀️ foncier ».
- **Actions** : « Prochaine action recommandée » (`nextAction`) mise en avant + boutons
  `Button` variants (primary=**Envoyer**, secondary=Valider, ghost=Modifier, danger=Écarter/
  Oublier). **Aucun envoi sans validation explicite.**
- **2/3** : Pourquoi ce score (+ encart warn hors-cible), Satellite, Bornes IRVE, Fil mail,
  Assistant réponse, Appel à froid, Éditeur e-mail. **1/3** : Entreprise, Décideur, Historique
  & notes (timeline d'événements avec icône par type).
- **Mobile** : tout en 1 colonne ; barre d'actions **sticky bas d'écran**.

### C. Tableau de bord — `app/(app)/tableau-de-bord/page.tsx` (+ `reprise-banner`)
Écran de pilotage — la dataviz doit briller (Stripe/Vercel), nette en clair **et** sombre.
- **Contexte** : `RepriseBanner` soigné (objectif final, client actif, deadlines, résumé) =
  vrai point d'entrée « où on en est / ce qu'on vise ».
- **Données** : 5 `Stat` (Leads · Top≥75 · Taux réponse · Taux rebond · Coût ; chiffres
  tabulaires, micro-tendance ▲/▼ optionnelle) · « À traiter en priorité » (`DataTable`,
  `ScoreBadge global`) · Distribution scores (`ProgressBar` top/mid/low) · Relances dues ·
  Potentiels solaires · Funnel (Envoyés→Ouverts→Répondus→Rebonds) · Meilleurs départements.
- Cohérence des couleurs funnel ↔ statuts ↔ distribution.

---

## 6. Plan d'exécution (jalons shippables, CI verte à chaque fois)

- **D1 — Design system** : `globals.css` v2 (alias historiques conservés) + dark mode (toggle
  dans `/compte`) + Geist + lucide + logo boussole + composants `ui/`. **Aucun écran retouché.**
- **D2 — Prospects** · **D3 — Fiche lead** · **D4 — Tableau de bord** : restyle avec le DS.
- **D5 — Rebrand + polish** : « ReSign CRM » → « RénoBoost » (nav, `<title>`, login,
  welcome-modal) + logo, polish mobile (375px), guide associé 1 page, retrait du code mort.

**Definition of done (chaque jalon)** : `npm run typecheck` + `npm run build` verts, `next
lint` propre, contraste AA clair + sombre, focus clavier visible, **zéro régression** sur les
écrans non retouchés, captures avant/après dans la PR (draft).

---

## 7. Comment démarrer
Lis ce brief, propose un défaut pour les 5 décisions ouvertes (§4.7), présente le plan D1→D5,
**attends mon feu vert**, puis attaque **D1** (design system, sans toucher aux pages). Branche :
`claude/magical-johnson-WWWgz`. Confirme le périmètre avant tout push/PR ; pas d'action
sortante sans validation.
