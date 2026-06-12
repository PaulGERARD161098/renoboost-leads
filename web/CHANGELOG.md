# Journal des versions — RénoBoost Leads

**Convention** : chaque PR livrée incrémente le **mineur** (`1.x.0`). La version
affichée (page de connexion + header, à côté de la boussole) progresse donc
**V1.0 → V1.1 → V1.2 …**. Source de vérité : `web/lib/version.ts` (`APP_VERSION`),
complétée par le SHA du build Vercel.

| Version | PR | Contenu |
|---|---|---|
| **1.15.0** | #147 | **Multi-contacts par rôle** : table `lead_contacts` (migration `0041`) + bloc « Interlocuteurs » sur la fiche (ajout, ★ principal, suppression). Le principal est recopié dans `leads.contact_*` (compat pipeline) et son **rôle adapte le ton du brouillon** : DAF → ROI/aides, DG → stratégie/APER, énergie → exploitation/technique |
| **1.14.0** | #146 | **File d'appels du jour** : l'accueil ouvre sur « qui j'appelle ce matin, et pourquoi » — top 10 priorisé (réponses chaudes > bascule téléphone > relances dues > top leads jamais contactés), angle d'attaque en une phrase, téléphone cliquable (`tel:`) ou accès fiche pour enrichir |
| **1.13.0** | #145 | **Références chantiers — preuve sociale géolocalisée** : table `references_chantiers` (migration `0040`) gérée depuis /cibles (ville géocodée via la BAN) ; le brouillon cite automatiquement la référence la plus proche du prospect sur l'axe du mail (« nous avons équipé X à N km ») — jamais de référence inventée |
| **1.12.0** | #144 | **Issue de RDV — boucle d'apprentissage** : statuts `gagne`/`perdu` + raison de clôture (boutons 🏆/✖️ sur la fiche après réponse ou RDV), colonne « Gagnés » au kanban /suivi, compteurs Gagnés/Perdus (/suivi + tableau de bord) · l'**angle du brouillon** est persisté (`leads.mail_angle`) pour les futures stats par angle. Migration `0039` |
| **1.11.0** | #143 | **Calibrage de la fiche Cible** : le champ « Signaux recherchés » devient un textarea **un signal par ligne** (fini le découpage sur les virgules qui cassait les phrases — la fiche Rossini avait 2 signaux coupés en 4, réparés en base) |
| **1.10.0** | #142 | **Analyse d'image → prospect** : chaque entreprise identifiée sur une capture GMaps se convertit en 1 clic en lead « à valider » — pré-scoré (terrain de l'image → potentiels v2 via les mêmes scorers, croisé avec le comptage IRVE), accroche Magellan en brouillon de mail, dédoublonnage par nom (« déjà en pipeline → fiche »). Migration `0038` (`image_analyses.leads`) |
| **1.9.0** | #141 | **Draine les retours d'Henry** : le prompt des mails interdit explicitement les axes faibles (<4/10) et fait primer l'analyse du site sur l'angle L4 (fini le mail « ombrières » sur un site 0/10) · angle du brouillon affiché sur la fiche (ou alerte « sans analyse ») · **vue satellite élargie** (~640 m) en 2ᵉ passe pour les grands sites invisibles à 260 m (web + worker) · **téléphone** sous la signature des emails (`app_context.telephone`, migration `0037`, éditable au bandeau Reprise) |
| **1.8.0** | #132 | Décompte du coût **par API** (Google Places · Pappers · Dropcontact · Claude). La donnée par étage du moteur (`RunStats`) est ventilée par le worker dans `runs.cout_detail` (migration `0036`) puis affichée — *progressive disclosure* — sur le **rapport de fin**, la **page recherche** et le **tableau de bord** (cumul tous runs). L'**estimation** avant lancement est aussi détaillée par poste. *(Ligne corrigée : étiquetée 1.6.0 par erreur à la livraison.)* |
| — | #140 | Reprise au login : deadlines de la couche contexte affichées *(livrée sans bump)* |
| — | #139 | Reply ⟶ action : action recommandée par catégorie + RDV pris pour les chauds *(livrée sans bump)* |
| — | #138 | Veille ⟶ Bornes : lancer une veille VE depuis une opportunité du radar *(livrée sans bump)* |
| — | #137 | Intentions ⟶ Recherche : intention ciblée surfacée sur le formulaire *(livrée sans bump)* |
| — | #136 | Bornes : croisement radar sous-équipement × potentiel pipeline *(livrée sans bump)* |
| — | #135 | Intentions ⟶ Veille : la Cible remonte l'intention réelle *(livrée sans bump)* |
| **1.7.0** | #134 | Cible par intention d'achat : presets flotte VE / conso élec / fiscal compilés en filtres + signaux, mémorisés dans `verticales.config.intentions` |
| **1.6.0** | #133 | Ciblage Rossini : découverte **SIRENE-first** opt-in (`decouverte_sirene_first`) + témoin hors-filtre dans `RunStats` |
| **1.5.2** | #131 | Nettoyage sécurité : vitest 2 → 4 (élimine la vuln critique + toute la chaîne esbuild/vite, dev-only). Audit 8 → 3 vulnérabilités. Les 3 restantes (next/postcss) préexistent et leur « fix » downgrade Next — laissées en l'état |
| **1.5.1** | #130 | Solidification : infra de test JS (vitest) + 32 tests unitaires sur les helpers purs (scoring 3 potentiels, garde-fous de ciblage, signaux VE) · nouveau job CI `web` (typecheck + vitest) — l'app Next est désormais vérifiée en CI |
| **1.5.0** | #129 | Interconnexion veille ↔ lead ↔ bornes : un signal VE lié rehausse le potentiel bornes à l'analyse (A) · bloc « Signaux de veille liés » sur la fiche lead (B) · lien croisé /solaire → radar Bornes VE (C) |
| **1.4.0** | #128 | Workspace /solaire : les **3 sous-scores** (☀️ toiture · 🅿️ ombrières · 🔌 bornes VE) affichés par site, axe le plus prometteur mis en relief + tri/filtre par axe (au lieu du seul score toiture) |
| **1.3.0** | #127 | Garde-fous au lancement d'une recherche : tranche d'effectif par preset (PME 10–250 par défaut, plafond honoré par le worker) + modale de validation « Voilà ce que tu vas lancer » avec alertes (ciblage ETI/grands groupes, budget) + validation serveur |
| **1.2.0** | #125 | Mail piloté par les 3 potentiels (meilleur + zone bornes + offre client) · LinkedIn dirigeant/entreprise dans la fiche · bouton « Enrichir le contact » on-demand |
| **1.1.0** | #124 | Économie de coût : Claude ne score plus les leads hors-filtre par défaut (coût L4 ÷~2-3) · versionnage V1.x par PR + ce journal |
| 1.0.x | #123 | Fiabilité runs (reaper + bouton Relancer + heartbeat continu) + rapport de fin de recherche |
| 1.0.x | #119 | Boucle réponse « valider & envoyer » + panneau Clés API |
| **1.0.0** | #115 | Nom du CRM en voyant de santé + affichage du numéro de version |
| — | #113 | Observabilité worker (heartbeat) |
