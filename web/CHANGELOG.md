# Journal des versions — RénoBoost Leads

**Convention** : chaque PR livrée incrémente le **mineur** (`1.x.0`). La version
affichée (page de connexion + header, à côté de la boussole) progresse donc
**V1.0 → V1.1 → V1.2 …**. Source de vérité : `web/lib/version.ts` (`APP_VERSION`),
complétée par le SHA du build Vercel.

| Version | PR | Contenu |
|---|---|---|
| **1.5.0** | #129 | Interconnexion veille ↔ lead ↔ bornes : un signal VE lié rehausse le potentiel bornes à l'analyse (A) · bloc « Signaux de veille liés » sur la fiche lead (B) · lien croisé /solaire → radar Bornes VE (C) |
| **1.4.0** | #128 | Workspace /solaire : les **3 sous-scores** (☀️ toiture · 🅿️ ombrières · 🔌 bornes VE) affichés par site, axe le plus prometteur mis en relief + tri/filtre par axe (au lieu du seul score toiture) |
| **1.3.0** | #127 | Garde-fous au lancement d'une recherche : tranche d'effectif par preset (PME 10–250 par défaut, plafond honoré par le worker) + modale de validation « Voilà ce que tu vas lancer » avec alertes (ciblage ETI/grands groupes, budget) + validation serveur |
| **1.2.0** | #125 | Mail piloté par les 3 potentiels (meilleur + zone bornes + offre client) · LinkedIn dirigeant/entreprise dans la fiche · bouton « Enrichir le contact » on-demand |
| **1.1.0** | #124 | Économie de coût : Claude ne score plus les leads hors-filtre par défaut (coût L4 ÷~2-3) · versionnage V1.x par PR + ce journal |
| 1.0.x | #123 | Fiabilité runs (reaper + bouton Relancer + heartbeat continu) + rapport de fin de recherche |
| 1.0.x | #119 | Boucle réponse « valider & envoyer » + panneau Clés API |
| **1.0.0** | #115 | Nom du CRM en voyant de santé + affichage du numéro de version |
| — | #113 | Observabilité worker (heartbeat) |
