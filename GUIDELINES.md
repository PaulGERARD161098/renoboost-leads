# mondpe-facile.fr — Design System

Design system for **mondpe-facile.fr**, a consumer-facing energy-renovation tool
edited by **RenoBoost IA** (EURL, 149 avenue du Maine, 75014 Paris).

Users search the **DPE** (*Diagnostic de Performance Énergétique*) of a home by
address, simulate the cost of renovation work, and calculate their aid
(MaPrimeRénov', CEE, éco-PTZ). An AI agent — **« Vitruve »** — guides them
through renovation decisions.

- **Audience:** French homeowners and buyers, often non-experts.
- **Tone:** pédagogique, rassurant, orienté action — with a streak of mischief.
- **Surfaces:** responsive marketing/tool website (Next.js), address search with
  interactive map, DPE result sheets, conversational AI assistant.
- **Regulatory subject:** the look must inspire trust on an official, ADEME-sourced topic.

## Sources

This system was reverse-engineered from the product's own codebase. If you have
access, explore these to build with higher fidelity:

- **GitHub (primary):** https://github.com/PaulGERARD161098/mon-dpe.fr — the live
  Next.js 15 / React 19 / TypeScript / Tailwind v3 / shadcn/ui app. Tokens lifted
  from `app/globals.css` + `tailwind.config.ts`; components from `components/ui/*`
  (shadcn) and `components/search/*`, `components/home/*`, `components/devis/*`.
- Related repos by the same author worth a look: `renoboost-leads`, `RenoboostIAV2`.
- `BRIEF.md` and `CLAUDE.md` in the repo describe product scope and working method.

> The repo is the source of truth. Screenshots are lossy — read the component code.

---

## CONTENT FUNDAMENTALS

How copy is written for mondpe-facile.fr.

- **Language:** French (`lang="fr"`). Métier vocabulary is used plainly: *DPE,
  GES, MaPrimeRénov', Loi Climat, ADEME, CEE, éco-PTZ, passoire (thermique),
  diagnostiqueur, étiquette énergétique*.
- **Address the user as "vous"** (formal-but-warm), often via imperatives:
  « **Saisissez une adresse** », « **Comptez sur Vitruve** ». First person appears
  for the user's inner monologue in headlines: « **Combien je perds chaque année ?** ».
- **Tone: pedagogical, direct, a little mischievous.** Real examples from the product:
  - « Trouvez votre DPE en un clic. »
  - « Arrêtez les frais. »
  - « Combien je perds chaque année ? » / « Le coût de l'inaction sur votre logement »
  - « passoire » (slang for an energy-leaking home — used unapologetically)
  - « Pause détente — Testez vos connaissances immo / chantier / réno »
- **Radical honesty about the AI.** Vitruve is never oversold: « Vitruve peut-il se
  tromper ? Oui. » The assistant is framed as a guide/conseiller, not an oracle.
- **Casing:** Sentence case for body and titles. **Section labels are UPPERCASE**
  with wide tracking (« OU LAISSEZ-VOUS GUIDER »). Badges are short and capitalized
  by meaning, not forced uppercase.
- **Punctuation & FR typography:** French apostrophes/quotes in content; numbers with
  French units and non-breaking context (`kWh/m²/an`, `kgCO₂/m²/an`, `1 000 €`).
- **Sourcing is explicit and repeated.** Official data always carries attribution:
  « Source : ADEME », « Données officielles ADEME — DPE des logements existants
  (post-juillet 2021) », « Géocodage Base Adresse Nationale ».
- **Emoji:** not used in product UI copy. (The repo's *docs* use ✅/🚧 as status
  markers, but the shipped interface relies on icons, not emoji.)
- **Vibe:** confident, plain-spoken, action-first. Short sentences. Every screen
  pushes toward a next step (search, simulate, claim aid, ask Vitruve).

### Verbatim copy library (reuse these exact strings)

- **Headlines:** « Trouvez votre DPE en un clic. » · « Trouvez ou rénovez votre
  logement avec Vitruve. » · « Arrêtez les frais. » · « Comptez sur Vitruve, votre
  agent IA en rénovation énergétique. » · « Ne rien faire, ça vous coûte cher. » ·
  « Pause détente — testez vos connaissances. »
- **CTAs:** Rechercher · Consulter mon DPE · Vitruve · Démarrer ma rénovation ·
  Estimer mes travaux et mes aides · Demander un devis travaux · Trouver mon
  logement · Faire faire un DPE · Imprimer / Enregistrer en PDF · Jouer maintenant ·
  Nouvelle conversation.
- **Error states:** « Le service ADEME ne répond pas — La recherche a expiré.
  Réessayez dans quelques instants. » · « Aucun DPE trouvé — Pas de DPE référencé à
  proximité de {adresse} dans la base ADEME (rayon jusqu'à 200 m). » · « Vous avez
  atteint la limite de 5 questions par jour. »
- **Empty states:** « Vous n'avez pas encore de demande enregistrée sur cet
  appareil. » · « Aucune adresse sélectionnée — Tapez une adresse dans la barre
  ci-dessus puis sélectionnez une suggestion. »
- **Recurring disclaimers:** « Estimations indicatives fondées sur des prix de
  marché 2025, hors aides, non contractuelles. » · « Les aides (MaPrimeRénov', CEE)
  ne sont pas déduites : votre reste à charge réel est souvent plus bas. » ·
  « mon-dpe.fr n'établit pas de diagnostics et ne se substitue pas à un
  diagnostiqueur certifié. »
- **Vitruve honesty (brand-defining):** « Vitruve peut-il se tromper ? Oui. Vitruve
  est une aide à la décision : pour tout engagement, faites confirmer par un
  diagnostiqueur ou un artisan certifié RGE. »

---

## VISUAL FOUNDATIONS

- **Palette — light & institutional.** A trustworthy white/slate base with a single
  confident green as the brand action color.
  - `primary` green `hsl(142 71% 45%)` ≈ `#2ecc71` — buttons, focus rings, links.
  - `foreground` `hsl(222 47% 11%)` — deep blue-slate text (`#0f172a`).
  - `muted`/`secondary` `hsl(210 40% 96%)` — pale blue-grey surfaces.
  - `border` `hsl(214 32% 91%)`, `destructive` `hsl(0 84% 60%)`.
  - Full **dark mode** maintained (slate `#0f172a` background, near-white text).
- **The 7 official DPE colors (A→G)** are a French State norm and are **non-negotiable,
  pixel-exact**: `#2c9c54 #52b153 #a8cd5a #f6ed3d #f6c83d #ec8e3d #d3322a`. A/B/F/G
  use white text; C/D/E use dark text (contrast).
- **« Vitruve » gradient is sacred.** The purple→fuchsia gradient
  (`purple-600 → fuchsia-600`, `#9333ea → #c026d3`) paired with the **Sparkles** icon
  is the *exclusive* identity of the AI. **Never** use it for ordinary UI.
- **Per-surface thematic gradients.** Beyond Vitruve, each major feature carries its
  own accent gradient for navigation coherence — use the right one per surface:
  - Rénovation / aides → emerald→teal (`#10b981 → #14b8a6`) — `/renovation`, devis CTAs.
  - Coût de l'inaction → rose→orange (`#e11d48 → #ea580c`) — `/cout-inaction`.
  - Recherche logement → sky→indigo (`#0ea5e9 → #6366f1`) — `/logement`.
  - Loi Climat → amber/gold (`#f59e0b → #d97706`) — `/guides/calendrier-climat`.
  - Jeux → emerald→green (`#10b981 → #16a34a`) — `/jeux`.
  - **Golden rule:** the violet→fuchsia is *only ever* Vitruve; never reuse it for these.
- **Typography:** system sans (no webfont). Titles `font-bold tracking-tight`;
  H1 `text-4xl`/`text-5xl`; section labels `text-sm font-medium uppercase tracking-wider`;
  badges `text-xs font-semibold`.
- **Corner radii — moderate, serious-but-accessible.** Base `--radius: 8px`. Cards
  `rounded-lg` (8px), buttons/inputs `rounded-md` (6px), badges/pills `rounded-full`,
  feature/“parcours” cards `rounded-xl`/`rounded-2xl` (12–16px). Nothing is overly round.
- **Backgrounds:** predominantly flat white/slate. **No decorative gradients on chrome.**
  Gradients are used in exactly two sanctioned places: (1) Vitruve, (2) soft tonal
  "parcours" cards on the home that use a *very low-opacity* accent wash
  (`bg-<tone>-500/5`) with a `border-2 border-<tone>-500/30` — a tinted-border-plus-faint-fill
  pattern, one accent per card (rose / indigo / amber / emerald / violet).
- **Cards:** `bg-card`, `1px` border, `shadow-sm`, `rounded-lg`, generous `p-6` padding.
  Light, calm elevation — never heavy drop shadows except popovers/menus (`shadow-lg`).
- **Imagery:** warm, real renovation photography (Pexels in the repo) — interiors,
  façades, worksites. Natural color, not heavily filtered. Used as supporting/feature
  imagery, not full-bleed hero washes on the core tool pages.
- **Animation:** restrained. `tailwindcss-animate`; a gentle hero headline rotation
  (`hero-message-in`: 0.5s ease, fade + 0.5rem rise; rotates every 2.8s). Accordion
  open/close 0.2s ease-out. **All motion respects `prefers-reduced-motion`** with a
  static stacked fallback.
- **Hover states:** primary button darkens (`hover:bg-primary/90`); secondary lightens
  (`/80`); ghost/outline gain a muted `accent` background; tonal cards deepen border
  and fill (`/30→/60`, `/5→/10`); links underline. **Press:** color shift only (no scale
  bounce) — keeps a serious, institutional feel.
- **Focus:** always visible — `focus-visible:ring-2 ring-ring ring-offset-2` (green ring).
  This is a hard accessibility rule, not optional.
- **Spacing:** roomy and airy. Home stacks sections with `gap-10`; cards `p-6`; content
  width capped (`max-w-2xl`/`max-w-3xl`) and centered for readability.
- **Transparency / blur:** used sparingly — tonal accent fills via `/5`–`/15` alpha,
  map popovers with a translucent dark panel. No glassmorphism on the core UI.
- **Accessibility baseline:** WCAG AA contrast, semantic HTML, decorative icons
  `aria-hidden`, energy labels exposed as `role="img"` with descriptive `aria-label`
  (e.g. "Classe DPE D sur 7").

---

## ICONOGRAPHY

- **Icon set: [lucide-react](https://lucide.dev)** — the only icon system in the
  product. Clean, consistent **2px-stroke outline** icons. No filled icon set, no
  custom icon font, no PNG sprites.
- **Default size** `size-4` (16px) inline / in buttons; `size-5`–`size-6` (20–24px) in
  feature tiles. Stroke inherits `currentColor`.
- **Icons seen in the codebase:** `Search`, `MapPin`, `Loader2` (spinner),
  `ArrowRight`, `ExternalLink`, `Sparkles` (Vitruve only), `TrendingDown`, `Home`,
  `Wrench`, `CalendarClock`, `ClipboardCheck`, `Gamepad2`.
- **Decorative icons** carry `aria-hidden`; meaningful ones get an `aria-label`.
- **Emoji:** not used as UI iconography. **Unicode** appears only as typographic glyphs
  (the `·` separators in the footer, `—` em-dashes, `²`/`₂` in units), never as icons.
- **In this design system,** load lucide from CDN:
  `<script src="https://unpkg.com/lucide@latest"></script>` then `lucide.createIcons()`.
  This matches the product's stroke weight and style exactly — no substitution needed.

There is **no logo mark** — the brand wordmark is the lowercase domain
**`mondpe-facile.fr`** set in bold system sans with tight tracking. The closest thing
to a brand symbol is the **Vitruve Sparkles** badge (gradient pill).

---

## Index — what's in this folder

| Path | What it is |
|---|---|
| `README.md` | This file — context, content & visual foundations, iconography. |
| `colors_and_type.css` | All design tokens: color (light/dark), DPE scale, Vitruve, type scale, radii, shadows. |
| `SKILL.md` | Agent-Skills front-matter so this system can be used in Claude Code. |
| `preview/` | Small specimen cards that populate the Design System tab. |
| `ui_kits/website/` | High-fidelity recreation of the website: tokens, components (JSX), and an interactive `index.html`. |
| `assets/img/` | Real renovation photography (Pexels) for feature/imagery use. |

### UI kits
- **`ui_kits/website/`** — the consumer site, recreated as an interactive multi-page
  prototype: home (rotating headline, address search, quick-access subnav, discovery
  grid), DPE result sheet with tabbed building details + neighbourhood map, the
  Vitruve chat (drawer + full page), works simulator, cost-of-inaction calculator,
  devis form, the **Faire faire un DPE** order tunnel + diagnostician list, and the
  quiz. Routed, French, light/dark, accessible.

> No slide template was provided, so no `slides/` were created.
