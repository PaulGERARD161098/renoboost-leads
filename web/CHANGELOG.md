# Journal des versions — RénoBoost Leads

**Convention** : chaque PR livrée incrémente le **mineur** (`1.x.0`). La version
affichée (page de connexion + header, à côté de la boussole) progresse donc
**V1.0 → V1.1 → V1.2 …**. Source de vérité : `web/lib/version.ts` (`APP_VERSION`),
complétée par le SHA du build Vercel.

| Version | PR | Contenu |
|---|---|---|
| **1.1.0** | #124 | Économie de coût : Claude ne score plus les leads hors-filtre par défaut (coût L4 ÷~2-3) · versionnage V1.x par PR + ce journal |
| 1.0.x | #123 | Fiabilité runs (reaper + bouton Relancer + heartbeat continu) + rapport de fin de recherche |
| 1.0.x | #119 | Boucle réponse « valider & envoyer » + panneau Clés API |
| **1.0.0** | #115 | Nom du CRM en voyant de santé + affichage du numéro de version |
| — | #113 | Observabilité worker (heartbeat) |
