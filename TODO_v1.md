# TODO V1 — ce qu'on garde pour APRÈS le 1er juin 2026

Toute idée hors V0 atterrit ici sans débat. On en reparle après livraison V0.

Voir `ROADMAP_V0.md` pour le périmètre V0 figé.

## Différenciants puissance (à prioriser ensuite)

### L0 — Détection terrain
- Google Solar API pour détection toitures exploitables
- IGN ortho-photo + CV pour détection parkings
- Cadastre.gouv.fr pour parcelles + propriétaires (DGFiP côté restreint)
- Branchement par verticale (activable / désactivable)
- Estimation surface, orientation, ombrage

### Signaux d'achat enrichis
- Levées de fonds BPI / sociétés de capital-risque
- Recrutement actif (Pôle Emploi, LinkedIn, sites carrière)
- Déménagement (BODACC, JO)
- Annonces d'investissement / CSRD
- Anniversaire OPCO / renouvellement contrats

### Cartographie multi-décideurs
- Au-delà du dirigeant principal data.gouv.fr
- Scraping LinkedIn ciblé (directeur technique, patrimoine, achats, RSE)
- Identification du décideur pertinent par verticale
- Profilage équipes via Dropcontact

### Multi-canal (LinkedIn + tél + mail)
- Séquences LinkedIn (Phantombuster ou équivalent)
- Appels guidés (script généré par l'agent)
- Combinaison canaux par lead selon profil

### Boucle de feedback IA
- L'agent apprend des réponses (qui répond, quel angle marche)
- Fine-tuning des prompts L4 selon retours
- Stats par verticale, par signal, par template

### Génération de séquences à la volée
- Briefer l'agent en 3 lignes → 3 mails personnalisables par lead
- Remplace les templates fixes par verticale en V0
- A/B testing automatique

## UX / produit

### Esthétique
- Charte graphique, design system
- Branding personnalisable par verticale ou par client utilisateur
- Logo, palettes, typo

### PWA installable
- Manifeste + service worker
- Icône d'accueil sur téléphone
- Mode offline pour consultation
- Notifications push (mail répondu, run terminé)

### Carte des leads
- Leaflet ou Mapbox
- Vue par verticale, par campagne, par score
- Filtres dynamiques par carte
- Heatmap densité

### Dashboard ROI
- Métriques Instantly remontées : envoyés / délivrés / ouverts /
  cliqués / répondus / RDV bookés
- ROI par verticale, par campagne, par template
- Comparatif inter-campagnes

### Multi-tenant complet
- Workspaces isolés par client utilisateur
- RBAC (admin / opérateur / lecteur)
- Quotas par workspace
- Clés API mutualisées ou propres au choix
- Facturation à l'usage

## Verticales B2C

- Pipeline B2C particulier (cadastre, propriétaires fonciers, listes
  nominatives achetées)
- RGPD B2C : consentement explicite, registre renforcé
- Sources spécifiques : Atlasoco, fichiers achetés, partenariats
- Détection terrain plus critique (toiture maison particulière)

## Robustesse / scale

### Sources alternatives data
- Pappers (payant, qualité +)
- INSEE Sirene API directe (volumes plus élevés)
- Pharow (DB FR enrichie)
- Cognism / Apollo (international)

### Vérification emails batch
- Intégration NeverBounce / ZeroBounce
- Vérification automatique avant envoi
- Coût ~5-10 €/1000 vérifs

### Warm-up domaine automatisé
- Détection statut domaine
- Refus lancement si non warmé
- Recommandation domaines sacrifiables

### Cache distribué
- Migration cache local SQLite → Redis ou Supabase
- Partage cache entre workspaces (anonymisé)

## Brique agent avancée

### Apprentissage par feedback
- L'utilisateur note les leads (top / non / hors cible)
- L'agent ajuste ses critères de scoring
- Personnalisation par utilisateur

### Mémoire long terme
- L'agent se souvient des préférences par utilisateur
- Suggestions proactives (« la dernière campagne sur compta avait X
  taux, on retente avec Y modification ? »)

### Agents spécialisés
- Agent prospecteur (créer verticales / campagnes)
- Agent rédacteur (drafts mails)
- Agent analyste (post-campagne, suggestions amélioration)

## Intégrations CRM

- Export vers HubSpot / Pipedrive / Salesforce / Brevo
- Synchronisation bidirectionnelle (réponses → CRM, statuts → app)
- Webhooks bidirectionnels

## Conformité avancée

### RGPD V1
- Portail droit d'accès / portabilité automatisé
- Anonymisation automatique après période
- Audit log inviolable

### Conformité internationale
- Adaptation US (CAN-SPAM)
- Adaptation UE hors FR (GDPR national)
- Adaptation CH

## Comment ajouter une entrée ici

Format minimal :
- 1-3 lignes max
- Section appropriée
- Pas de discussion en V0

L'évaluation et priorisation se font **après** le 1er juin.
