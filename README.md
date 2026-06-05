# Handoff — mondpe-facile.fr Design System

## Overview
This bundle is the **design system for mondpe-facile.fr** (DPE search, renovation
simulator, aids calculator, guided by the AI agent « Vitruve »), plus a
high-fidelity, interactive recreation of the consumer website. It was
reverse-engineered from the product's own repo
(`github.com/PaulGERARD161098/mon-dpe.fr`: Next.js 15, React 19, TypeScript,
Tailwind, shadcn/ui, lucide-react) and extended with new flows (a progressive
"Faire faire un DPE" lead funnel, neighbourhood map, etc.).

The goal of this handoff is to **fold the validated tokens and new components back
into the real Next.js repo** — not to ship the HTML.

## About the Design Files
The files under `design/` are **design references written in plain HTML + React
(Babel, CDN)** — prototypes showing the intended look and behaviour. They are
**not production code to copy verbatim**. Recreate them in the repo's existing
environment: shadcn/ui primitives, Tailwind classes, lucide-react icons, App
Router server/client components. Most foundations already exist in the repo —
this package mostly **confirms tokens** and **adds a few new components**.

## Fidelity
**High-fidelity.** Final colors, typography, spacing, radii, and interactions.
Recreate pixel-for-pixel using the repo's Tailwind theme and shadcn components.

---

## Design Tokens → where they live in the repo

All tokens already map to `app/globals.css` (HSL CSS vars) and
`tailwind.config.ts`. They are unchanged from the repo except the **new thematic
gradient tokens** (see below). Source of truth in this bundle: `design/tokens.css`.

### Semantic colors (HSL, light / dark) — `app/globals.css`
| Token | Light | Dark |
|---|---|---|
| `--primary` / `--ring` | `142 71% 45%` | idem |
| `--background` | `0 0% 100%` | `222 47% 11%` |
| `--foreground` | `222 47% 11%` | `210 40% 98%` |
| `--muted` / `--secondary` | `210 40% 96%` | `217 33% 17%` |
| `--muted-foreground` | `215 16% 47%` | `215 20% 65%` |
| `--border` / `--input` | `214 32% 91%` | `217 33% 17%` |
| `--destructive` | `0 84% 60%` | `0 63% 31%` |
| `--radius` | `0.5rem` | idem |

### Official DPE scale (A→G) — `tailwind.config.ts` `colors.dpe` (DO NOT change)
`A #2c9c54 · B #52b153 · C #a8cd5a · D #f6ed3d · E #f6c83d · F #ec8e3d · G #d3322a`
A/B/F/G → white text; C/D/E → `foreground` text. Official ADEME norm, pixel-exact.

### Vitruve (AI) gradient — reserved, never on standard UI
`from-purple-600 to-fuchsia-600` (`#9333ea → #c026d3`) + `Sparkles` icon.

### NEW — per-surface thematic gradients (add to `globals.css` / a `lib/gradients.ts`)
```css
--grad-renovation: linear-gradient(to right, #10b981, #14b8a6); /* emerald→teal */
--grad-inaction:   linear-gradient(to right, #e11d48, #ea580c); /* rose→orange  */
--grad-logement:   linear-gradient(to right, #0ea5e9, #6366f1); /* sky→indigo   */
--grad-climat:     linear-gradient(to right, #f59e0b, #d97706); /* amber/gold   */
--grad-jeux:       linear-gradient(to right, #10b981, #16a34a); /* emerald→green*/
```
Rule: violet→fuchsia is Vitruve only; never reuse it for these.

### Typography
System sans (no webfont). Titles `font-bold tracking-tight`; H1 `text-4xl sm:text-5xl`;
H2 `text-2xl font-semibold tracking-tight`; section labels
`text-sm font-medium uppercase tracking-wider`; badges `text-xs font-semibold`.

### Radii / shadow
`rounded-lg` 8px (cards), `rounded-md` 6px (buttons/inputs), `rounded-full`
(badges), `rounded-xl`/`rounded-2xl` 12–16px (feature cards). `shadow-sm` cards;
`shadow-lg` popovers; map popups `0 8px 24px rgba(0,0,0,0.4)`.

---

## Components

### Existing (already in repo — confirm, don't recreate)
`components/ui/{button,badge,card,input}.tsx` (shadcn), plus
`components/search/{dpe-label,dpe-result-card,address-search-bar}.tsx`,
`components/home/rotating-headline.tsx`, `components/devis/vitruve-cta.tsx`.
The prototypes mirror these — use the repo versions.

### NEW or extended (implement / port)
| Component | Suggested path | Notes |
|---|---|---|
| **OrderDpeFunnel** | `components/faire-dpe/order-dpe-funnel.tsx` | Progressive 9-step lead funnel. See "Faire faire un DPE" below. |
| **DiagnosticianList** | `components/faire-dpe/diagnostician-list.tsx` | Certified diagnostician cards (rating, delay, price, "Certifié"). |
| **TrustBar** | `components/faire-dpe/trust-bar.tsx` | 4,8/5 · avis · couverture France · délai RDV. |
| **NeighborsSection** | `components/map/neighbors-section.tsx` (exists for MapLibre) | Prototype uses a stylised street-map; in prod keep MapLibre + IGN. Markers colored by DPE class; hover popup uses the `.mdf-popup` style already in `globals.css`. |
| **BuildingDetailsTabs** | `components/building-details/*` (exist) | Tabs: Détails / Quartier / Risques / Historique on the DPE result. |
| **ClimateLawBanner** | `components/building-details/climate-law-banner.tsx` (exists) | Red banner for F/G. |
| **CoutInactionCalculator / Simulateur / GuessrGame** | exist in repo | Prototypes confirm layout & copy. |

---

## Key flow — "Faire faire un DPE" (the main new work)

A **progressive lead funnel** ("Obtenez votre devis en 1 minute") that maximises
collected info before asking for contact details. Inspired by the UX flow of
DPE-ordering services — **original design in mondpe-facile.fr's brand**, not a copy.

**9 steps, one decision each, with a progress bar (Étape X/9 + %):**
1. Type de bien — choice cards (Appartement / Maison), auto-advance
2. Projet — Vendre / Louer / Rénover / M'informer
3. Détails — surface (m²) + nombre de pièces
4. Période de construction — Avant 1948 / 1948–1974 / 1975–2000 / Après 2000
5. Chauffage principal — Gaz / Électrique / Fioul / PAC / Bois / Autre
6. Localisation — code postal + ville (**prefilled** from the searched address when
   the funnel is entered from the "Aucun DPE trouvé" state)
7. Créneau — Dès que possible / Sous 2 semaines / Ce mois-ci / Flexible
8. **Récap "Votre devis est prêt"** — price (à partir de 99 € appart / 149 € maison)
   + chips summarising every answer
9. **Coordonnées (last)** — prénom, téléphone, email + opt-in consent

**Patterns:** choice cards auto-advance on click; a reassurance strip under every
step ("Diagnostiqueur certifié · DPE opposable 10 ans · Données jamais revendues");
contact requested only at the end. Entry points: home subnav + the "Aucun DPE
trouvé" result CTA. Pair with `DiagnosticianList` below the funnel.

## Interactions & Behavior
- **Rotating headline**: 3 messages, 2.8s, fade+rise (`hero-message-in`), respects
  `prefers-reduced-motion` (static stacked fallback).
- **Vitruve**: floating button (purple→fuchsia, `animate-ping` halo) + side drawer +
  full chat page (`/renovation`): suggestion chips, "réfléchit…", feedback ↑/↓,
  honest disclaimer "Vitruve peut se tromper."
- **Address search**: BAN autocomplete, debounce 250ms, ARIA combobox, keyboard nav.
- **DPE result**: tabs Détails/Quartier/Risques/Historique; ClimateLawBanner for F/G.
- **Neighbours map**: markers colored by DPE class; hover → dark slate popup
  (`.mdf-popup`: bg `rgba(15,23,42,0.96)`, border `rgba(255,255,255,0.12)`,
  radius 8, shadow `0 8px 24px rgba(0,0,0,0.4)`).

## Accessibility (non-negotiable)
French `lang="fr"`, WCAG AA contrast, visible green focus ring
(`focus-visible:ring-2 ring-ring ring-offset-2`), decorative icons `aria-hidden`,
energy labels `role="img"` + descriptive `aria-label`, full dark mode.

## Copy
Use the verbatim strings in the root `README.md` → CONTENT FUNDAMENTALS (headlines,
CTAs, error/empty states, disclaimers, Vitruve honesty). Tone: pédagogique, direct,
un peu malicieux.

## Assets
- `assets/img/` — renovation photography (Pexels) for feature imagery.
- Icons: **lucide-react** (already a dependency). No custom icon set.

## Files in this bundle
- `design/index.html` — interactive website recreation (open in a browser).
- `design/*.jsx`, `design/kit.css`, `design/tokens.css`, `design/data.js` — the
  prototype source (React via Babel/CDN).
- `design/preview/` — small specimen cards (tokens & components).
- `tokens.css` — the design tokens (same as `design/tokens.css`).
- `assets/img/` — imagery.
- Root project `README.md` + `SKILL.md` — full guidelines (content, visual
  foundations, iconography). Read these first.

> A developer who wasn't in this conversation should be able to implement from this
> README + the root README.md alone.
