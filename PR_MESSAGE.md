# feat(design-system): tokens, UI kit & "Faire faire un DPE" funnel

> Copier-coller ce message dans la PR (ou comme prompt à Claude Code dans le repo).
> Référence complète : `design_handoff_design_system/README.md` + `GUIDELINES.md`.

## Résumé
Ajout du **design system mondpe-facile.fr** (tokens validés, guidelines, UI kit
interactif) et de nouveaux parcours, dont un **funnel de génération de leads
« Faire faire un DPE »**. Le bundle `design_handoff_design_system/` est une
**référence de design** (HTML/React via CDN) à recréer avec nos patterns
(Next.js App Router, shadcn/ui, Tailwind, lucide-react) — pas du code à livrer tel quel.

Règles non négociables : violet→fuchsia **réservé à Vitruve** ; couleurs DPE A→G
**officielles, intactes** ; focus ring vert visible ; `lang="fr"` ; **dark mode** complet ;
contraste WCAG AA.

---

## 1. Tokens — `app/globals.css` / `tailwind.config.ts`
- Couleurs sémantiques, échelle DPE (`colors.dpe`), radius : **déjà présents** → vérifier seulement.
- **AJOUT** : dégradés thématiques par surface (à mettre en CSS vars ou `lib/gradients.ts`)
  ```css
  --grad-renovation: linear-gradient(to right, #10b981, #14b8a6); /* emerald→teal */
  --grad-inaction:   linear-gradient(to right, #e11d48, #ea580c); /* rose→orange  */
  --grad-logement:   linear-gradient(to right, #0ea5e9, #6366f1); /* sky→indigo   */
  --grad-climat:     linear-gradient(to right, #f59e0b, #d97706); /* amber/gold   */
  --grad-jeux:       linear-gradient(to right, #10b981, #16a34a); /* emerald→green*/
  ```
  Règle d'or : ne jamais réutiliser le violet→fuchsia (Vitruve) pour ces surfaces.

## 2. Nouveaux composants à créer
| Composant | Chemin suggéré | Détail |
|---|---|---|
| `OrderDpeFunnel` | `components/faire-dpe/order-dpe-funnel.tsx` | Funnel progressif 9 étapes (voir §4). |
| `DiagnosticianList` | `components/faire-dpe/diagnostician-list.tsx` | Cartes diagnostiqueurs (note, délai, prix, badge « Certifié »). |
| `TrustBar` | `components/faire-dpe/trust-bar.tsx` | 4,8/5 · 1 240 avis · couverture France · RDV sous 48 h. |
| Page | `app/faire-faire-dpe/page.tsx` | Assemble TrustBar + funnel + liste ; pré-remplit l'adresse. |

## 3. Composants à enrichir (existants)
- `components/map/neighbors-section.tsx` — marqueurs colorés par classe DPE + **popup au survol** (style `.mdf-popup` déjà dans `globals.css` : fond `rgba(15,23,42,0.96)`, bord `rgba(255,255,255,0.12)`, radius 8, ombre `0 8px 24px rgba(0,0,0,0.4)`). En prod : garder MapLibre + IGN.
- Fiche DPE (`app/dpe/[numero]` / `components/building-details/*`) — onglets **Détails / Quartier / Risques / Historique** ; `ClimateLawBanner` (rouge) pour les classes **F/G**.
- Home (`app/page.tsx`) — carte **« Pause détente »** (jeux) bien visible + barre d'accès rapide (Faire faire un DPE / Estimer mes travaux / Coût de l'inaction / Jeux).

## 4. Funnel « Faire faire un DPE » (nouveau, pièce maîtresse)
Funnel progressif « Obtenez votre devis en 1 minute », pensé pour **collecter un
maximum d'infos avant la demande de contact**. Inspiré de la logique de parcours des
services de commande de DPE — **design original dans notre charte**, pas une copie.

9 étapes, une décision par écran, barre de progression (Étape X/9 + %) :
1. Type de bien (Appartement / Maison) — cartes cliquables, auto-avance
2. Projet (Vendre / Louer / Rénover / M'informer)
3. Détails (surface m² + nombre de pièces)
4. Période de construction (Avant 1948 / 1948–1974 / 1975–2000 / Après 2000)
5. Chauffage (Gaz / Électrique / Fioul / PAC / Bois / Autre)
6. Localisation (CP + ville) — **pré-rempli** depuis l'adresse cherchée (état « Aucun DPE trouvé »)
7. Créneau (Dès que possible / Sous 2 semaines / Ce mois-ci / Flexible)
8. **Récap « Votre devis est prêt »** (prix dès 99 € appart / 149 € maison + chips de synthèse)
9. **Coordonnées en dernier** (prénom, téléphone, email + opt-in)

Patterns : cartes de choix qui font avancer automatiquement ; **bandeau de réassurance**
à chaque étape (« Diagnostiqueur certifié · DPE opposable 10 ans · Données jamais
revendues »). Points d'entrée : barre d'accès rapide home + CTA de l'état « Aucun DPE trouvé ».

## 5. Interactions & accessibilité
- Accroche rotative (3 messages, 2,8 s, fade `hero-message-in`) — **contraste renforcé en dark
  mode** (texte quasi-blanc teinté indigo/emerald/rose), respect `prefers-reduced-motion`.
- Vitruve : bouton flottant (halo `animate-ping`) + tiroir + page chat `/renovation`
  (suggestions, « réfléchit… », feedback ↑/↓, disclaimer « Vitruve peut se tromper »).
- Recherche d'adresse : autocomplete BAN, combobox ARIA, nav clavier.
- A11y : focus ring vert, icônes déco `aria-hidden`, étiquettes énergie `role="img"`
  + `aria-label`, dark mode partout.

## 6. Copy
Réutiliser les chaînes verbatim de `GUIDELINES.md` → CONTENT FUNDAMENTALS
(accroches, CTAs, états d'erreur/vides, disclaimers, honnêteté Vitruve).
Ton : pédagogique, direct, un peu malicieux.

## Checklist de revue
- [ ] Dégradés thématiques ajoutés ; violet→fuchsia non détourné
- [ ] Couleurs DPE A→G intactes (pixel-exact)
- [ ] Funnel `OrderDpeFunnel` : 9 étapes, coordonnées en dernier, pré-remplissage adresse
- [ ] `TrustBar` + `DiagnosticianList` + page `/faire-faire-dpe`
- [ ] Popup carte `.mdf-popup` ; bannière loi Climat F/G ; carte jeux sur la home
- [ ] Contraste accroches rotatives OK en light **et** dark
- [ ] A11y : focus rings, `aria-hidden`, `aria-label`, `lang="fr"`, dark mode
- [ ] `pnpm format && pnpm lint && pnpm typecheck && pnpm build` au vert
