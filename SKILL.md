---
name: mondpe-facile-design
description: Use this skill to generate well-branded interfaces and assets for mondpe-facile.fr (consumer energy-renovation / DPE tool by RenoBoost IA, with the AI agent « Vitruve »), either for production or throwaway prototypes/mocks. Contains essential design guidelines, colors, type, the official DPE color scale, the reserved Vitruve gradient, and UI kit components for prototyping.
user-invocable: true
---

Read the `README.md` file within this skill, and explore the other available files
(`colors_and_type.css`, `preview/`, `ui_kits/website/`).

If creating visual artifacts (slides, mocks, throwaway prototypes, etc.), copy assets
out and create static HTML files for the user to view. If working on production code,
copy assets and read the rules here to become an expert in designing with this brand.

Hard rules to never break:
- The 7 **DPE colors (A→G)** are an official French norm — reproduce them pixel-exact.
- The **purple→fuchsia « Vitruve » gradient + Sparkles icon** is the exclusive identity
  of the AI. Never use it for ordinary UI.
- French language (`lang="fr"`), WCAG AA contrast, visible green focus rings, decorative
  icons `aria-hidden`. Maintain full dark mode.
- Tone: pédagogique, direct, un peu malicieux. Honest about the AI.

If the user invokes this skill without other guidance, ask what they want to build or
design, ask a few clarifying questions, and act as an expert designer who outputs HTML
artifacts _or_ production code, depending on the need.
