# 01 — Design System · RénoBoost

> Spécification de la **fondation** : tokens, mode sombre, typographie, icônes, composants de
> base partagés. Construite **à partir de l'existant** (`app/globals.css`, `lib/ui.ts`) pour
> garantir la cohérence. Inclut une proposition **complète et concrète** de `globals.css` v2
> (Tailwind v4, syntaxe `@theme`).
>
> Règle d'or : **un seul endroit de vérité = les tokens.** Aucun composant ne hardcode une
> couleur hex ou une taille « à la main » ; tout passe par les variables.

---

## 1. Couleurs

### 1.1 Marque — vert RénoBoost (le `#1f7a4d` actuel devient `brand-600`)
Nuancier construit autour du vert existant pour ne **rien casser** (le brand actuel reste
reconnaissable) tout en offrant des nuances pour hover/focus/fonds/bordures.

| Token | Hex | Usage |
|---|---|---|
| `brand-50`  | `#ecf6f0` | fonds très clairs, bandeaux |
| `brand-100` | `#d3ead d` *(d3eadd)* | fonds de pastille, hover doux |
| `brand-200` | `#a8d6bd` | bordures douces |
| `brand-300` | `#74bd97` | éléments désaturés |
| `brand-400` | `#3f9e6f` | icônes secondaires |
| `brand-500` | `#27885a` | accent clair |
| `brand-600` | `#1f7a4d` | **brand actuel — couleur primaire, boutons, liens actifs** |
| `brand-700` | `#176040` | hover bouton |
| `brand-800` | `#155c39` | **= --brand-dark actuel**, pressed |
| `brand-900` | `#0f4b2e` | textes sur fond clair, dark-mode accent |
| `brand-950` | `#08301d` | fonds dark mode |

### 1.2 Accent solaire (secondaire) — ambre
Réutilise l'ambre déjà présent (`scoreVerdict` « potentiel correct », ☀️ solaire). Usage
**parcimonieux** : highlights, potentiel solaire, CTA secondaire.

`solar-400 #f5b740` · `solar-500 #e29a17` · `solar-600 #c27c0a` (texte sur clair).

### 1.3 Neutres (légèrement chauds — influence Notion)
Repris/affinés depuis l'existant. Garder la **proximité** avec `#f7f8fa`/`#e6e8ec`/`#687076`.

| Token | Clair | Rôle |
|---|---|---|
| `bg`            | `#f7f8fa` | fond app (= existant) |
| `bg-subtle`     | `#eef0f3` | zones alternées, table head |
| `card`          | `#ffffff` | surface carte (= existant) |
| `border`        | `#e6e8ec` | bordure standard (= existant) |
| `border-strong` | `#d3d6db` | séparateurs marqués |
| `text`          | `#11181c` | texte principal (= existant) |
| `text-muted`    | `#687076` | texte secondaire (= existant `--muted`) |
| `text-subtle`   | `#9aa0a6` | placeholders, légendes |

### 1.4 Statuts (sémantique — **mapping 1:1 avec `lib/ui.ts`, à préserver**)
On conserve exactement les couleurs métier déjà en place ; on les **promeut en tokens** pour
éviter les paires `bg-X-100/text-X-800` éparpillées.

| Statut lead | Token | Équivalent actuel |
|---|---|---|
| `nouveau`   | `status-neutral` | slate-100 / slate-700 |
| `a_valider` | `status-warn`    | amber-100 / amber-800 |
| `valide`    | `status-info`    | blue-100 / blue-800 |
| `envoye`    | `status-sent`    | indigo-100 / indigo-800 |
| `ouvert`    | `status-open`    | violet-100 / violet-800 |
| `repondu`   | `status-success` | emerald-100 / emerald-800 |
| `a_relancer`| `status-alert`   | orange-100 / orange-800 |
| `ecarte`    | `status-muted`   | slate-200 / slate-500 |

Score : `score-top` (emerald, ≥75) · `score-mid` (amber, ≥50) · `score-low` (slate).
Runs : `demande`=neutral · `en_cours`=info · `termine`=success · `echoue`=danger(red).

### 1.5 Mode sombre
Toutes les variables ci-dessus ont un pendant `.dark`. Principe **Vercel/Linear** : fonds
quasi-noirs légèrement bleutés, surfaces élevées plus claires, brand viré vers `brand-400/500`
pour rester lisible.

`bg #0b0d0f` · `bg-subtle #14171a` · `card #16191d` · `border #262b30` · `text #e8eaed`
· `text-muted #9aa0a6` · brand actif → `brand-500`.

---

## 2. Typographie

- **Police** : *Geist* via `next/font` (fallback `-apple-system, Segoe UI, Roboto, sans-serif`).
  Chiffres **tabulaires** activés pour la dataviz (tableau de bord, scores, montants).
- **Échelle** (rythme cohérent, remplace les `text-*` ad hoc) :

| Token | Taille / interligne | Usage |
|---|---|---|
| `display` | 30 / 36, bold | titre de page hero (login, accueil) |
| `h1` | 24 / 32, bold | titre de page (= `text-2xl font-bold` actuel) |
| `h2` | 18 / 28, semibold | sous-section |
| `eyebrow` | 12 / 16, semibold, uppercase, tracking-wide | **titre de section** (= pattern actuel) |
| `body` | 14 / 20 | texte courant (= `text-sm`) |
| `body-lg` | 16 / 24 | texte confort (fiches) |
| `caption` | 12 / 16 | légendes, métadonnées |
| `mono` | 13 / 20, mono | SIREN, codes, montants techniques |

---

## 3. Espacement, rayons, ombres, motion

- **Espacement** : échelle 4-pt (`4 8 12 16 24 32 48`). Padding carte standard = `16` (`p-4`),
  carte dense = `12`. Gap grille = `16`/`24`.
- **Rayons** : `sm 8px` (chips, inputs) · `md 12px = rounded-xl actuel` (cartes) ·
  `lg 16px = rounded-2xl` (bandeaux ActionsBand) · `full` (pastilles, avatars).
- **Ombres** (discrètes, esprit Linear) : `shadow-sm` (hover carte) · `shadow-md` (sidebar
  dépliée, popovers) · `shadow-lg` (modales). Pas d'ombres lourdes par défaut.
- **Motion** : transitions `150ms ease-out` (hover/couleur), `200ms` (largeur sidebar — déjà
  en place). `prefers-reduced-motion` respecté. Pas d'animation gratuite.

---

## 4. Icônes — **sortir des emojis**

- Adopter **un seul** jeu vectoriel. Recommandation : **lucide-react** (léger, tree-shakeable,
  esprit Linear/Notion, MIT). Alternative zéro-dépendance : sprite SVG maison.
- **Table de correspondance** (emoji actuel → icône lucide) pour migration sans perte de sens :

| Emoji | Sens | lucide |
|---|---|---|
| 🧭 | boussole / cap / Magellan | `Compass` (devient le logo) |
| 👥 | prospects | `Users` |
| 📊 | suivi | `BarChart3` |
| ✉️ | campagnes / mail | `Mail` |
| 🔌 | bornes VE | `Plug` / `PlugZap` |
| 🔎 | recherches | `Search` |
| 🎯 | cibles | `Target` |
| 📈 | tableau de bord | `LineChart` |
| 🤖 | agent | `Bot` |
| 📖 | mode d'emploi | `BookOpen` |
| ⚙️ | compte | `Settings` |
| 🔥 | priorité | `Flame` |
| ☀️ | potentiel solaire | `Sun` |
| ⏰ | relances | `Clock` |
| 🔔 | veille / signal | `Bell` |
| 🔄 | run en cours | `RefreshCw` (animé) |
| ⏻ | déconnexion | `LogOut` |
| ★ | action apprise | `Star` |

> Le ☀️ « potentiel solaire » peut **rester** comme marqueur métier expressif si Paul préfère —
> à trancher écran par écran dans `02`. Le reste passe en vectoriel.

---

## 5. Composants de base partagés (à extraire dans `web/components/ui/`)

Aujourd'hui dispersés/dupliqués (`Stat`, `FilterChip`, `FunnelBar` redéfinis dans chaque page).
On les centralise. API minimale proposée :

| Composant | Remplace / unifie | Props clés |
|---|---|---|
| `<Card>` / `<CardHeader>` | `rounded-xl border bg-white` répété partout | `tone?` (default/brand/warn), `interactive?` |
| `<SectionTitle>` | l'`<h2 class="eyebrow">` + emoji répété | `icon`, `count?`, `action?` |
| `<StatusBadge status>` | usages directs de `LEAD_STATUS_COLOR` | branché sur tokens §1.4 |
| `<ScoreBadge score variant>` | `scoreColor` + `scoreVerdict` inline | `commercial \| solaire \| global` |
| `<Stat label value icon? trend?>` | `Stat` du tableau de bord | + variation (▲/▼) optionnelle |
| `<Button variant size>` | boutons/`<Link>` stylés à la main | `primary \| secondary \| ghost \| danger` |
| `<FilterChip active>` | `FilterChip` (inbox) | active state via tokens |
| `<DataTable>` | les `<table>` répétées | colonnes typées, tri, hover, empty |
| `<EmptyState icon title cta>` | les blocs `border-dashed` répétés | message + action |
| `<ProgressBar value tone>` | barres run/funnel/distribution | une seule impl |
| `<ActionsBand>` (revisité) | déjà existant — re-skin tokens | inchangé fonctionnellement |

**Règle de migration** : on n'introduit un composant `ui/` que s'il est utilisé ≥2 fois ;
sinon il reste local. Pas de sur-abstraction.

---

## 6. `globals.css` v2 — proposition concrète (Tailwind v4)

> À **proposer** en D1, pas appliqué encore. Les noms de variables restent rétro-compatibles
> (`--bg`, `--card`, `--border`, `--text`, `--muted`, `--brand`, `--brand-dark` conservés en
> alias) pour ne casser aucun écran existant pendant la transition.

```css
@import "tailwindcss";

@theme {
  /* Marque */
  --color-brand-50:  #ecf6f0;
  --color-brand-100: #d3eadd;
  --color-brand-200: #a8d6bd;
  --color-brand-300: #74bd97;
  --color-brand-400: #3f9e6f;
  --color-brand-500: #27885a;
  --color-brand-600: #1f7a4d; /* brand historique */
  --color-brand-700: #176040;
  --color-brand-800: #155c39; /* brand-dark historique */
  --color-brand-900: #0f4b2e;
  --color-brand-950: #08301d;

  /* Accent solaire */
  --color-solar-400: #f5b740;
  --color-solar-500: #e29a17;
  --color-solar-600: #c27c0a;

  /* Rayons / ombres */
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;

  /* Police */
  --font-sans: var(--font-geist), -apple-system, "Segoe UI", Roboto, sans-serif;
}

:root {
  /* Sémantique — clair */
  --bg: #f7f8fa;
  --bg-subtle: #eef0f3;
  --card: #ffffff;
  --border: #e6e8ec;
  --border-strong: #d3d6db;
  --text: #11181c;
  --muted: #687076;        /* alias historique conservé */
  --text-subtle: #9aa0a6;

  --brand: var(--color-brand-600);       /* alias historique */
  --brand-dark: var(--color-brand-800);  /* alias historique */
  --brand-contrast: #ffffff;

  --ring: var(--color-brand-500);
}

.dark {
  --bg: #0b0d0f;
  --bg-subtle: #14171a;
  --card: #16191d;
  --border: #262b30;
  --border-strong: #333a41;
  --text: #e8eaed;
  --muted: #9aa0a6;
  --text-subtle: #6b7177;

  --brand: var(--color-brand-500);
  --brand-dark: var(--color-brand-700);
  --brand-contrast: #07130c;

  --ring: var(--color-brand-400);
}

html, body {
  background: var(--bg);
  color: var(--text);
  -webkit-font-smoothing: antialiased;
  font-feature-settings: "tnum" 1; /* chiffres tabulaires pour la dataviz */
}

* { box-sizing: border-box; }

/* Focus clavier visible et cohérent (accessibilité) */
:focus-visible {
  outline: 2px solid var(--ring);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  * { transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; }
}
```

> Statuts (§1.4) : deux options d'implémentation à trancher en D1 — soit **garder les classes
> Tailwind** `bg-emerald-100…` dans `lib/ui.ts` (zéro risque, recommandé pour cette passe),
> soit les remapper sur des tokens `--status-*`. Défaut : **garder `lib/ui.ts`**, juste relire
> les contrastes en dark.

---

## 7. Option « shadcn/ui » (note de décision)

Non retenu pour cette passe (cf. cadrage §9.3). À réévaluer ensuite si on a besoin de
primitives accessibles (Dialog, Dropdown, Toast, Combobox). Si adopté un jour : il se branche
sur les **mêmes tokens** ci-dessus (variables CSS), donc le présent design system reste valable.

---

## 8. Checklist d'intégration (à cocher en D1)

- [ ] `globals.css` v2 en place, alias historiques conservés, **build vert sans toucher aux pages**.
- [ ] Police Geist câblée via `next/font` dans `app/layout.tsx`.
- [ ] `lucide-react` ajouté ; logo boussole + icônes de nav migrées.
- [ ] Toggle dark mode (classe `.dark` sur `<html>`, persistée) + respect `prefers-color-scheme`.
- [ ] Composants `ui/` extraits : `Card`, `SectionTitle`, `StatusBadge`, `ScoreBadge`, `Stat`,
      `Button`, `FilterChip`, `EmptyState`, `ProgressBar`.
- [ ] Contrastes AA revérifiés en clair **et** sombre.
