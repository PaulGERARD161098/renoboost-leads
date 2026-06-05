# 02 — Specs des 3 écrans clés · RénoBoost

> Spécification détaillée des écrans re-stylés en D2→D4, **à partir de l'existant** (chaque
> écran référence le fichier source actuel). Pour chacun : rôle · pattern agent-first ·
> anatomie · états · responsive · recette (DoD). On **re-style** et on **réorganise**, on ne
> change pas le métier.
>
> Invariant transverse (charte CLAUDE.md) : **Contexte (où on en est) → Actions recommandées
> → Données**. C'est l'ordre vertical de chaque page.

---

## A. Prospects / Inbox
**Source** : `app/(app)/inbox/page.tsx` + `components/{actions-band,run-group,leads-table,
run-card}.tsx`. **C'est l'écran principal de l'associé.**

### Rôle
File de prospects à traiter, comme un triage d'e-mails. Deux vues : **groupée par recherche**
(défaut) et **à plat** (filtres statut/texte/canal).

### Pattern agent-first (déjà amorcé, à renforcer visuellement)
1. **Contexte** : bandeau run en cours (barre de progression live) + résumé « X à traiter ».
2. **Actions** : `ActionsBand` (« Réponses à traiter », « Leads à valider », « Relances dues »,
   « Appels à passer », « Signaux de veille ») — re-skin tokens, étoile = action apprise.
3. **Données** : groupes par recherche (`RunGroup`) ou table à plat (`LeadsTable`).

### Anatomie cible
- **En-tête** : `h1` « Prospects » + sous-titre ; à droite, toggles **Vue par recherche /
  Vue à plat / Archivées** → migrer en `<Button variant="secondary">` cohérents.
- **ActionsBand** : carte `rounded-lg` accent brand (gradient `brand-50`→transparent),
  puces = `<Button ghost>` avec compteur en `<Badge>`. Icône lucide en tête (`Compass`).
- **Run en cours** : carte `status-info` avec `<ProgressBar tone="info">` (remplace la barre
  bleue inline). Icône `RefreshCw` animée.
- **Groupe par recherche** (`RunGroup`) : carte dépliable. Header = nom cible + `zoneLabel` +
  compteurs (`total`, `top ≥75` en `score-top`, `hors-filtre`). Divulgation progressive.
- **Table à plat** (`LeadsTable`) : `<DataTable>` partagé — colonnes Entreprise · Ville ·
  Score (`<ScoreBadge>`) · Statut (`<StatusBadge>`) ; ligne cliquable → fiche ; hover discret.
- **Chips de filtre** : `<FilterChip>` partagé (au lieu du local), tokens brand.

### États
- **Vide (aucune recherche)** : `<EmptyState icon={Search}>` → CTA « Lancer une recherche ».
- **Vide (filtre sans résultat)** : message + « effacer le filtre ».
- **Erreur de chargement** : encart `danger` lisible (existe déjà, re-skin).
- **Chargement** : skeleton de lignes (nouveau, esprit Linear) plutôt qu'écran blanc.

### Responsive (mobile = usage terrain prioritaire)
- Sidebar repliée ; en-tête actions empilées.
- Table → **liste de cartes** sous `md` : chaque lead = carte (nom + ville + ScoreBadge +
  StatusBadge), tap = fiche. Cibles tactiles ≥ 44px.

### Recette
- [ ] Pattern Contexte→Actions→Données visible sans scroll sur desktop.
- [ ] `ScoreBadge`/`StatusBadge`/`FilterChip` partagés (plus de styles inline).
- [ ] Vue mobile = cartes, pas de scroll horizontal.
- [ ] Zéro emoji (📞 → `Phone`, 🔄 → `RefreshCw`, 🧭 → `Compass`).

---

## B. Fiche lead
**Source** : `app/(app)/leads/[id]/page.tsx` + `components/{lead-editor,lead-status-actions,
lead-notes,lead-relance,satellite-panel,mail-thread,reply-assistant,cold-call-panel,
bornes-links}.tsx`. **L'associé y passe 90 % du temps.**

### Rôle
Tout pour décider et agir sur un prospect : score expliqué, contact, e-mail pré-rédigé,
échange, relance, appel, timeline.

### Pattern agent-first
1. **Contexte** : bloc « hero » = score + verdict commercial (`scoreVerdict`) + score global
   (commercial + ☀️ foncier satellite).
2. **Actions** : « Prochaine action recommandée » (`nextAction`) + `LeadStatusActions`
   (Valider/Envoyer/Écarter/Oublier) + `LeadRelance`. **Aucun envoi sans validation.**
3. **Données** : pourquoi-ce-score, satellite, bornes, fil mail, appel, éditeur, identité,
   décideur, historique.

### Anatomie cible
- **Fil d'Ariane** « ← Retour aux prospects » → garder, style `text-muted` + icône `ChevronLeft`.
- **En-tête** : `h1` entreprise + secteur·ville·CP ; `<StatusBadge>` à droite.
- **Hero score** (carte `rounded-lg`, 2 colonnes desktop) :
  - Gauche : pastille score 80×80 (`<ScoreBadge size="lg">`), libellé « Score d'intérêt »,
    verdict, `<ProgressBar>`, ligne « global / commercial / ☀️ foncier ».
  - Droite : « Prochaine action recommandée » mise en avant + boutons d'action (`<Button>`
    variants : primary=Envoyer, secondary=Valider, ghost=Modifier, danger=Écarter/Oublier).
- **Colonne principale (2/3)** : cartes empilées — *Pourquoi ce score* (+ encart `warn`
  hors-cible), *Satellite*, *Bornes IRVE*, *Fil mail* (`MailThread`), *Assistant réponse*
  (si message entrant), *Appel à froid*, *Éditeur e-mail*.
- **Colonne latérale (1/3)** : *Entreprise*, *Décideur*, *Historique & notes* (timeline =
  `lead_events`, icône par type d'événement via la table de correspondance du DS).

### États
- 404 si lead introuvable (existe).
- Champs vides → `—` (existe, garder).
- `score_raison` absent → message pédagogique (existe).
- Hero responsive : colonnes empilées sous `md` (déjà géré, vérifier rythme).

### Responsive
- Tout en une colonne sous `lg` ; hero score empilé sous `md`.
- Boutons d'action en barre **sticky bas d'écran** sur mobile (pouce) — amélioration proposée.

### Recette
- [ ] Hero = `ScoreBadge` + `ProgressBar` partagés ; boutons = `<Button>` variants.
- [ ] Timeline avec icônes vectorielles par type d'événement.
- [ ] Action principale (Envoyer) atteignable au pouce sur mobile.
- [ ] Dark mode lisible (verdicts, encarts warn/danger).

---

## C. Tableau de bord
**Source** : `app/(app)/tableau-de-bord/page.tsx` + `components/reprise-banner.tsx`.
**Écran de pilotage** — c'est ici que la dataviz doit briller (boussole Stripe/Vercel).

### Rôle
Santé du pipeline + prochaines actions au login (couche contexte : objectif, deadlines,
client actif, résumé de session).

### Pattern agent-first
1. **Contexte** : `RepriseBanner` (objectif final, client actif, deadlines, résumé généré) —
   c'est la « reprise au login » de la charte. À soigner : c'est la première chose vue.
2. **Actions** : puces « Réponses à traiter / Leads à valider / Relances dues » + alerte veille.
3. **Données** : stats, priorités, distribution scores, relances, solaire, funnel, départements.

### Anatomie cible
- **RepriseBanner** : carte hero accent brand, claire et calme (pas criarde). Icône `Compass`.
- **Rangée de stats** : 5 × `<Stat>` partagé (Leads · Top ≥75 · Taux réponse · Taux rebond ·
  Coût) — ajouter une **micro-tendance** optionnelle (▲/▼ vs période) et chiffres tabulaires.
- **À traiter en priorité** (2/3) : `<DataTable>` top 8 par score global, `<ScoreBadge global>`.
- **Distribution des scores** (1/3) : 3 `<ProgressBar>` (top/mid/low) aux couleurs score.
- **Relances à faire** : table, dates en `status-alert`/rose.
- **Potentiels solaires** : table, `<ScoreBadge variant="solaire">` (garder ☀️ si Paul aime).
- **Funnel d'envoi** : `<FunnelBar>` partagé (Envoyés→Ouverts→Répondus→Rebonds), couleurs
  cohérentes avec les statuts (indigo/violet/emerald/rose).
- **Meilleurs départements** : `<DataTable>` (Dépt · Leads · Score moyen · Top).

### États
- Pipeline vide → stats à 0 + `<EmptyState>` invitant à lancer une recherche.
- Pas de contexte (`app_context` vide) → RepriseBanner propose de définir objectif/client.

### Responsive
- Stats : 2 colonnes mobile → 5 desktop (déjà géré).
- Grilles 2/3–1/3 → empilées sous `lg`.

### Recette
- [ ] `Stat`, `ProgressBar`, `FunnelBar`, `DataTable` = composants partagés (zéro duplication).
- [ ] Chiffres tabulaires alignés ; dataviz nette en clair **et** sombre.
- [ ] RepriseBanner = vrai point d'entrée « où on en est / ce qu'on vise ».
- [ ] Cohérence des couleurs funnel ↔ statuts ↔ distribution.

---

## D. Composants transverses touchés (rappel `01`)
`Card` · `SectionTitle` · `StatusBadge` · `ScoreBadge` · `Stat` · `Button` · `FilterChip` ·
`DataTable` · `EmptyState` · `ProgressBar` · `ActionsBand` (re-skin). Tous dans
`components/ui/`, branchés sur les tokens de `globals.css` v2.

## E. Recette globale des 3 écrans
- [ ] Même grammaire visuelle (espacements, rayons, ombres, titres de section).
- [ ] Pattern Contexte→Actions→Données respecté partout.
- [ ] `typecheck` + `build` verts, `lint` propre, captures avant/après dans la PR.
- [ ] Aucune régression sur les 7 écrans non retouchés (héritage tokens).
