# 03 — Prompts prêts à coller · chantier design RénoBoost

> Prompts **autoportants** : un Claude qui ouvre une session neuve doit pouvoir démarrer sans
> autre question que les portes ouvertes. Ils référencent les fichiers de cadrage `00`/`01`/`02`.
> Ordre d'usage : **P0 (kickoff) → P1 (design system) → P2/P3/P4 (écrans) → P5 (rebrand/polish)
> → PR (garde-fou cohérence)**. Coller un bloc à la fois.

---

## P0 — Kickoff / validation du cadrage (à lancer en premier)

```
Projet : RénoBoost-Leads, repo renoboost-leads, app web dans web/ (Next.js 15, React 19,
Tailwind v4 fait-main, Supabase, déploy Vercel). On démarre un CHANTIER DESIGN : faire passer
l'interface commerciale partagée (Paul admin + son associé commercial) d'« utilitaire » à
« produit crédible en clientèle ».

Lis d'abord, dans l'ordre, ces fichiers de cadrage (ne code rien avant) :
  web/docs/design/00_CADRAGE_DESIGN.md   (vision, décisions, principes, plan)
  web/docs/design/01_DESIGN_SYSTEM.md    (tokens, dark mode, icônes, composants)
  web/docs/design/02_ECRANS_CIBLES.md    (specs Prospects / Fiche lead / Tableau de bord)

Décisions déjà prises : marque = RénoBoost (abandon « ReSign CRM ») ; direction = mix
Linear+Attio/Pipedrive+Notion+Stripe/Vercel ANCRÉ dans l'existant ; périmètre 1re passe =
design system + 3 écrans clés ; métaphore boussole 🧭/Magellan.

Avant de coder, tranche avec moi les 5 décisions ouvertes du §9 de 00_CADRAGE_DESIGN.md
(police, dark mode, shadcn, accent solaire, profondeur rebrand) en me proposant un défaut
pour chacune. Puis présente le plan D1→D5 et attends mon feu vert. Branche de travail :
claude/magical-johnson-WWWgz. Pas d'action sortante sans validation.
```

---

## P1 — D1 : Design system (fondation, aucun écran retouché)

```
D1 du chantier design RénoBoost. Implémente la FONDATION sans toucher aux pages existantes
(elles doivent rester intactes par héritage). Référence : web/docs/design/01_DESIGN_SYSTEM.md.

1. Réécris web/app/globals.css en v2 (proposition §6 du DS) : nuancier brand 50→950 autour du
   #1f7a4d existant (= brand-600), accent solaire, neutres chauds, tokens sémantiques, focus
   visible, prefers-reduced-motion. CONSERVE les alias historiques (--bg,--card,--border,
   --text,--muted,--brand,--brand-dark) pour ne casser aucun écran.
2. Ajoute le mode sombre (.dark sur <html>, persistance localStorage + respect
   prefers-color-scheme au 1er chargement), plus un toggle (placé dans /compte).
3. Câble la police Geist via next/font dans app/layout.tsx (fallback system), chiffres
   tabulaires activés.
4. Ajoute lucide-react ; crée le logo « boussole » et prépare la table de correspondance
   emoji→icône (DS §4) — sans encore migrer les écrans.
5. Extrais dans web/components/ui/ les composants partagés (DS §5) : Card, SectionTitle,
   StatusBadge, ScoreBadge, Stat, Button, FilterChip, EmptyState, ProgressBar. Branche-les sur
   les tokens. StatusBadge/ScoreBadge réutilisent la sémantique de lib/ui.ts (ne change pas les
   couleurs métier).

Contraintes : npm run typecheck + npm run build verts, next lint propre, zéro régression
visuelle sur les écrans non retouchés, contrastes AA clair ET sombre. Commit clair, push sur
claude/magical-johnson-WWWgz, ouvre une PR draft avec captures. Ne retouche AUCUNE page écran
dans ce jalon.
```

---

## P2 — D2 : Écran Prospects / Inbox

```
D2 du chantier design RénoBoost. Re-style l'écran PROSPECTS avec le design system de D1.
Source + spec : app/(app)/inbox/page.tsx et web/docs/design/02_ECRANS_CIBLES.md §A.

Objectifs : appliquer le pattern Contexte→Actions→Données ; remplacer les styles inline par les
composants ui/ (Card, ScoreBadge, StatusBadge, FilterChip, ProgressBar, EmptyState, Button) ;
re-skin ActionsBand et la carte « run en cours » (ProgressBar + icône RefreshCw animée) ;
migrer tous les emojis en icônes lucide ; ajouter des skeletons de chargement ; sur mobile,
basculer la table de leads en liste de cartes (cibles ≥44px, pas de scroll horizontal).

Ne change pas le métier ni les requêtes Supabase. typecheck+build verts, lint propre. Capture
avant/après desktop + mobile dans la PR. Push claude/magical-johnson-WWWgz.
```

---

## P3 — D3 : Écran Fiche lead

```
D3 du chantier design RénoBoost. Re-style la FICHE LEAD. Source + spec :
app/(app)/leads/[id]/page.tsx et web/docs/design/02_ECRANS_CIBLES.md §B.

Objectifs : hero score avec ScoreBadge size=lg + ProgressBar partagés + verdict commercial +
score global (commercial + ☀️ foncier) ; bloc « Prochaine action recommandée » mis en avant ;
boutons d'action en <Button> variants (primary=Envoyer, secondary=Valider, ghost=Modifier,
danger=Écarter/Oublier) — RAPPEL : aucun envoi sans validation explicite ; timeline d'événements
avec icônes vectorielles par type ; sur mobile, barre d'actions sticky en bas d'écran.

Ne touche pas aux Server Actions d'envoi/relance/RGPD ni à la logique. typecheck+build verts,
dark mode lisible (verdicts + encarts warn/danger). Capture avant/après. Push
claude/magical-johnson-WWWgz.
```

---

## P4 — D4 : Tableau de bord (focus dataviz)

```
D4 du chantier design RénoBoost. Re-style le TABLEAU DE BORD. Source + spec :
app/(app)/tableau-de-bord/page.tsx et web/docs/design/02_ECRANS_CIBLES.md §C.

Objectifs : soigner RepriseBanner comme vrai point d'entrée « où on en est / ce qu'on vise » ;
rangée de 5 Stat partagés avec chiffres tabulaires (+ micro-tendance optionnelle) ; remplacer
les Stat/FunnelBar/DataTable dupliqués localement par les composants ui/ partagés ; cohérence
des couleurs funnel ↔ statuts ↔ distribution ; dataviz nette en clair ET sombre (boussole
Stripe/Vercel). Garder ☀️ comme marqueur métier solaire si pertinent.

Ne change pas les agrégations/requêtes. typecheck+build verts, lint propre. Capture avant/après
clair + sombre. Push claude/magical-johnson-WWWgz.
```

---

## P5 — D5 : Rebrand + polish + doc

```
D5 du chantier design RénoBoost. Finalise le rebrand léger et le polish.

1. Remplace « ReSign CRM » par « RénoBoost » partout dans l'app (sidebar/nav.tsx, <title>
   metadata, page de login, welcome-modal) + logo boussole.
2. Passe de cohérence mobile sur Inbox et Fiche lead (375px).
3. Rédige web/docs/design/GUIDE_ASSOCIE.md : 1 page, comment l'associé utilise l'outil au
   quotidien (traiter un lead, envoyer, relancer, lire le tableau de bord), captures.
4. Retire le code mort laissé par les 4 jalons (composants locaux remplacés, imports inutiles).

typecheck+build verts, lint propre. Déploie sur Vercel. Mets à jour le CHANGELOG. Push
claude/magical-johnson-WWWgz et passe la PR en « prêt à relire ».
```

---

## PR — Garde-fou cohérence (revue avant merge de chaque jalon)

```
Relis le diff de la PR courante du chantier design RénoBoost contre web/docs/design/01 et 02.
Vérifie : (a) aucun hex/taille hardcodé hors tokens ; (b) composants ui/ réutilisés (pas de
re-duplication de Stat/FilterChip/FunnelBar) ; (c) statut = couleur + texte (jamais couleur
seule) ; (d) focus clavier visible, cibles tactiles ≥44px ; (e) contraste AA clair + sombre ;
(f) zéro emoji décoratif sur les écrans retouchés ; (g) pattern Contexte→Actions→Données
respecté ; (h) aucune régression sur les 7 écrans non retouchés. Liste les écarts en checklist
actionnable, puis corrige les points sûrs et signale les points à arbitrer.
```

---

### Note d'usage
- Ces prompts vivent dans le repo : un futur Claude les retrouve via `web/docs/design/`.
- Adapter le nom de branche si le chantier migre de branche.
- Respecter la charte CLAUDE.md : proposer un plan avant tout changement structurant, confirmer
  le périmètre avant push/PR/merge, jamais d'action sortante sans validation.
