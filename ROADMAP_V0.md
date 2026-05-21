# ROADMAP V0 — cible 1er juin 2026

Document de pilotage de la livraison V0 « plateforme de prospection B2B
pivotable par verticale, agent-first, utile pas belle ».

## Calendrier d'ensemble

| Phase | Période | Statut |
|---|---|---|
| Cadrage / réflexion (pas de code) | jeu 21 mai — dim 24 mai | **En cours** |
| Sprints de développement | lun 25 mai — dim 31 mai | À démarrer D1 |
| V0 en ligne + démo | lun 1er juin | Livraison |

**Charge estimée** : 50-65 h de code sur 7 jours soit 7-9 h/jour. Tenable
si focus, agressif sans.

## Périmètre V0 — figé

### Inclus

- Pipeline L1→L4 existant (Places + SIREN + emails + scoring Claude)
- Agent IA copilote 13 outils (existant)
- Objet `Verticale` 1ʳᵉ classe + dossier `verticales/` (NOUVEAU)
- Objet `Campagne` distinct + dossier `campagnes/` (NOUVEAU)
- Agent discovery conversationnel pour générer une verticale (NOUVEAU)
- Wizard Streamlit agent-driven (chemin nominal) + mode expert YAML
  (NOUVEAU pour wizard, existant pour YAML)
- Perso mail lead-par-lead (lecture site web + tone verticale) (NOUVEAU)
- Vue mobile Streamlit lisible (responsive, pas PWA) (AMÉNAGEMENT)
- 3 verticales d'exemple câblées (solaire-pme, ombrieres, irve-flottes)
  (NOUVEAU contenu, structure existante)
- 1 run pilote réel bout-en-bout (PROCESS)
- Cold mailing Instantly avec staging N2 (existant)
- Persistance Supabase + auth password (existant)

### Exclus (TODO_v1.md)

- L0 détection terrain (Google Solar API, IGN ortho, cadastre)
- Carte des leads (Leaflet / Mapbox)
- Dashboard ROI par campagne
- PWA installable
- Multi-tenant complet (RBAC, workspaces isolés)
- LinkedIn multi-canal
- Signaux d'achat (BPI, JO, recrutement, déménagement)
- Cartographie multi-décideurs profonde
- Esthétique / design / branding
- B2C particulier (cadastre, listes nominatives, consentement explicite)
- Génération de séquences à la volée par l'IA (templates fixes par
  verticale en V0)

## Principes de conception

1. **Agent-first** : l'agent IA est le canal nominal d'interaction.
   Streamlit affiche, l'agent pilote. Pas de site statique à formulaires.
2. **Pivotable** : objet `Verticale` 1ʳᵉ classe, sélecteur de verticale
   en haut de l'app, switch 1 clic.
3. **Deux rails** : chemin nominal pour utilisateur lambda (wizard chat
   agent), mode expert pour utilisateur technique (YAML / CLI direct).
4. **Honnêteté des taux** : afficher les vrais taux de match, de bounce,
   de coût. Pas de sur-promesse.
5. **Validation humaine cold mail** : staging N2 obligatoire, rien ne
   part sans clic.
6. **Tests verts non négociables** : 617+ tests à maintenir, on monte
   vers 650+.
7. **Utile pas belle** : pas d'esthétique en V0. L'UX vient du dialogue
   agent, pas du CSS.

## Architecture cible V0

```
src/renoboost_leads/
  verticale/                      # NOUVEAU — objet 1ère classe
    __init__.py
    loader.py                     # charge verticales/<slug>/verticale.yaml
    schema.py                     # validation JSON Schema
    generator.py                  # agent → YAML depuis dialogue libre
  campagne/                       # NOUVEAU
    __init__.py
    loader.py                     # charge campagnes/<id>/campagne.yaml
    runner.py                     # instancie une verticale sur une zone
  agent/
    prompts/
      system.md                   # MODIFIÉ — ajouter contexte verticale active
      discovery.md                # NOUVEAU — prompt discovery conversationnelle
    tools/
      verticales.py               # NOUVEAU — list_verticales, get_verticale,
                                  #          create_verticale_from_brief, ...
      campagnes.py                # NOUVEAU — create_campagne_on_verticale
  stage4_prospection/
    enricher.py                   # MODIFIÉ — perso lead-par-lead (lecture
                                  #          site web + tone verticale)
  stage3_5_enrichment/
    site_reader.py                # NOUVEAU — lecture page d'accueil site
                                  #          web du lead pour signaux

verticales/                       # NOUVEAU dossier racine
  solaire-pme-toitures/
  ombrieres-parkings-grandes-surfaces/
  irve-flottes-b2b/

campagnes/                        # NOUVEAU dossier racine
  (vide initialement, peuplé par les runs)

app.py                            # MODIFIÉ — sélecteur verticale, onglet
                                  #          wizard chat
```

## Rétro-planning jour par jour

### Phase cadrage (21-24 mai, pas de code)

**D-3 vendredi 22 mai** — Affiner verticales V0
- Valider les 3 verticales choisies (slug + brief de chaque)
- Compléter `VERTICALES.md` avec premier jet de chaque `verticale.yaml`
- Lister les sources signaux requises par verticale (V0 = texte libre,
  V1 = API)

**D-2 samedi 23 mai** — Affiner schéma et tests
- Finaliser schéma `verticale.yaml` (champs + défauts)
- Préparer 3 briefs de test pour D2 (discovery agent)
- Définir critères de succès du run pilote D5 (taux match attendu,
  nb leads top, coût plafond)

**D-1 dimanche 24 mai** — Kickoff prompt
- Finaliser le prompt de démarrage D1 (section 9 de ce doc)
- Relire `PRE_MORTEM.md`, `VERTICALES.md`, `CLAUDE.md`
- Valider le périmètre une dernière fois
- Préparer environnement (clés API à jour, budgets vérifiés)

### Phase développement (25-31 mai)

**D1 lundi 25 mai** — Dé-solarisation + objet Verticale
- Créer module `src/renoboost_leads/verticale/` (loader, schema)
- Créer dossier `verticales/` à la racine
- Migrer configs existantes ombrières en `verticales/ombrieres-...`
- Ajouter validation JSON Schema des `verticale.yaml`
- Tests : ouverture / chargement / validation des 3 verticales
- **Livrable** : `python -m renoboost_leads.cli verticales list` fonctionne
- **PR draft** : `feat(verticales): objet Verticale 1ère classe (D1)`
- **Charge** : 6-8 h

**D2 mardi 26 mai** — Agent discovery conversationnel
- Prompt `agent/prompts/discovery.md`
- Nouvel outil agent `create_verticale_from_brief(brief: str)` et
  `refine_verticale(slug: str, instruction: str)`
- L'agent mène une discovery 5-10 échanges et produit un YAML valide
- Tests : 3 briefs typés (solaire, IRVE, ombrières) → 3 YAML valides
- **Livrable** : depuis le chat agent, créer une verticale en conversation
- **PR draft** : `feat(agent): discovery conversationnelle verticales (D2)`
- **Charge** : 8-10 h *(plus risqué — voir R2 du PRE_MORTEM)*

**D3 mercredi 27 mai** — Wizard Streamlit (1/2) + objet Campagne
- Onglet Streamlit « Nouvelle campagne » avec chat agent intégré
- Sélecteur verticale active en haut de l'app
- Objet `Campagne` et dossier `campagnes/`
- Le wizard chat propose verticale → zone → volume → budget → résumé
- Pas encore de lancement
- **Livrable** : depuis le navigateur, générer une `campagne.yaml`
- **PR draft** : `feat(wizard): onboarding chat agent + objet Campagne (D3)`
- **Charge** : 8 h

**D4 jeudi 28 mai** — Wizard (2/2) + perso lead-par-lead
- Bouton « Lancer » dans le wizard → lance pipeline en arrière-plan
- Progress L1→L4 affichée
- Module `site_reader.py` : lit page d'accueil + 1 page "à propos" du
  lead, extrait 2-3 signaux
- L4 enricher utilise signaux + tone verticale dans le pitch
- **Livrable** : campagne complète déclenchée depuis le mobile/desktop
- **PR draft** : `feat(perso): lecture site web + pitch personnalisé (D4)`
- **Charge** : 10 h

**D5 vendredi 29 mai** — Run pilote réel #1 + bug fixes
- Run réel verticale solaire-pme sur 1 département, 50 leads cible
- Mesurer : taux match SIREN, taux email, qualité pitch, coût
- Fix tout ce qui casse
- Premier draft mail validé puis envoyé (1 mail, vérifier réception)
- **Livrable** : 1 verticale prouvée bout-en-bout
- **PR draft** : `fix: corrections post-pilote #1 (D5)`
- **Charge** : 8-10 h

**D6 samedi 30 mai** — Run pilote réel #2 + démo pivot
- Run réel verticale ombrieres ou irve sur autre zone
- Démo pivot : switch verticale en 1 clic + relance
- Mobile responsive : adapter Streamlit pour téléphone (sidebar
  collapsable, boutons gros)
- **Livrable** : 2ᵉ verticale prouvée, pivot démontré
- **PR draft** : `feat(mobile): responsive + pivot inter-verticales (D6)`
- **Charge** : 6-8 h

**D7 dimanche 31 mai** — Polish minimal + edge cases
- 3ᵉ verticale câblée (IRVE-flottes ou autre selon retours D5/D6)
- Edge cases identifiés D5/D6 corrigés
- Tests verts confirmés, RGPD vérifié, registres OK
- README V0 mis à jour
- **Livrable** : V0 complet et testé
- **PR draft** : `feat: V0 ready for demo (D7)`
- **Charge** : 6 h

**D-day lundi 1er juin** — Livraison V0
- Run de démo complet (depuis le téléphone idéalement)
- Tag `v0.12.0` ou `v1.0.0-rc1`
- Bilan : ce qui marche, ce qui reste pour V1
- **Charge** : 2-3 h

## Critères d'acceptation V0

V0 est livré si **tous** ces critères sont remplis :

1. ✅ L'app est en ligne (Streamlit Cloud avec auth) et accessible depuis
   un téléphone
2. ✅ Depuis le téléphone, un utilisateur peut converser avec l'agent
   pour créer une verticale en < 10 minutes
3. ✅ Depuis le téléphone, l'utilisateur peut lancer une campagne sur
   une verticale en < 3 minutes
4. ✅ Au moins 2 verticales différentes ont fait l'objet d'un run réel
   produisant des leads exploitables
5. ✅ Au moins 1 cold mail a été validé via staging N2 et envoyé via
   Instantly (en dry-run minimum, idéalement réel sur 1 mail test)
6. ✅ Les pitchs L4 montrent une personnalisation visible (référence au
   secteur + ville + signal du site web)
7. ✅ Tests verts (650+ attendus)
8. ✅ RGPD : registre par session OK, opt-out présent dans les mails
9. ✅ Coût d'un run typique (200 leads, Haiku) reste sous 15 €

V0 **n'est PAS livré** si :
- Aucun cold mail n'a été drafté + validé bout-en-bout
- L'agent discovery ne produit pas de YAML valide sur > 50 % des briefs
- Le téléphone ne peut pas lancer une campagne (ergonomie cassée)

## Prompt de kickoff D1 (lundi 25 mai matin)

À coller dans une nouvelle session Claude Code lundi matin :

```
Contexte projet : repo renoboost-leads (Python), plateforme générique
de prospection B2B en cours de pivot vers une architecture pivotable
par verticale. Branche de travail :
claude/prospecting-automation-platform-9mq8j.

État au démarrage D1 :
- Cadrage V0 finalisé pendant le weekend 22-24 mai.
- Documents de cadrage à consulter EN PREMIER avant tout code :
  * CLAUDE.md (section "Cible V0 — 1er juin 2026")
  * ROADMAP_V0.md (rétro-planning + critères d'acceptation)
  * VERTICALES.md (définition canonique + schéma + 3 verticales V0)
  * PRE_MORTEM.md (15 risques + règles dures + mitigations)
- Pipeline L1-L4 fonctionnel, agent IA 13 outils, Streamlit déployé,
  Instantly staging N2 opérationnel, 617 tests verts.
- Aucune ligne de code applicatif modifiée depuis le 21 mai.

Sprint D1 (aujourd'hui) — Objet Verticale 1ère classe :
1. Créer module src/renoboost_leads/verticale/ (loader, schema, tests)
2. Créer dossier verticales/ à la racine du repo
3. Migrer configs existantes : config/client_ombrieres*.yaml devient
   verticales/ombrieres-parkings-grandes-surfaces/verticale.yaml +
   templates_sequence/ + pitch_l4.md
4. Ajouter validation JSON Schema des verticale.yaml
5. CLI : `python -m renoboost_leads.cli verticales list` + `show <slug>`
6. Tests : 5-10 nouveaux tests sur le module verticale

Livrable D1 : depuis la CLI, on liste et inspecte les verticales
disponibles. Le pipeline existant continue à marcher sans régression.

PR draft : `feat(verticales): objet Verticale 1ère classe (D1)`.

Règles dures (cf PRE_MORTEM.md) :
- Tests verts en fin de journée non négociable.
- Scope creep interdit : toute idée hors D1 va dans TODO_v1.md.
- Validation humaine avant push.

Commence par :
1. git status + git log --oneline -5
2. Relire ROADMAP_V0.md section "D1 lundi 25 mai"
3. Proposer un plan détaillé pour D1 (étapes + ordre + ~15 min de
   réflexion)
4. Attendre validation utilisateur avant de coder
```

## Suivi quotidien

Mettre à jour ce tableau chaque soir de sprint :

| Sprint | Date | Statut | Tests | PR | Notes |
|---|---|---|---|---|---|
| Cadrage | 21-24 mai | EN COURS | 617 verts | — | Réflexion 48-72h |
| D1 | 25 mai | — | — | — | — |
| D2 | 26 mai | — | — | — | — |
| D3 | 27 mai | — | — | — | — |
| D4 | 28 mai | — | — | — | — |
| D5 | 29 mai | — | — | — | — |
| D6 | 30 mai | — | — | — | — |
| D7 | 31 mai | — | — | — | — |
| V0 | 1er juin | — | — | — | — |
