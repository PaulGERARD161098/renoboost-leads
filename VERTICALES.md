# VERTICALES — définition canonique et architecture

Document de référence pour la conception V0 (cible 1er juin 2026).
À consulter avant tout travail touchant à `verticales/`, `campagnes/`,
ou au prompt système de l'agent.

## 1. Définition

Une **verticale** = *offre commerciale d'un client professionnel
utilisateur de l'outil*. C'est ce que le client vend, pas qui il cible.

**Exemples corrects** :
- « Installateur PV démarchant des PME industrielles à toiture > 200 m² »
- « Fabricant d'ombrières bois démarchant des grandes surfaces et retail parks »
- « Installateur IRVE démarchant des entreprises à flotte VE > 10 véhicules »
- « Applicateur peinture industrielle démarchant des usines agro et chimie »

**Exemples incorrects** (ce sont des cibles, pas des verticales) :
- « Cabinets d'expertise comptable »
- « Hypermarchés des Bouches-du-Rhône »
- « Avocats d'affaires »

Une verticale **encapsule en un seul objet** : offre + cibles types +
zone-type + signaux pertinents + ton mail + séquence + enrichissements
nécessaires.

## 2. Distinction verticale / campagne

| Objet | Réutilisable ? | Contenu | Exemple |
|---|---|---|---|
| **Verticale** | Oui (long terme) | Offre + cibles + ton + templates | `solaire-pme-toitures` |
| **Campagne** | Non (exécution ponctuelle) | Réf verticale + zone précise + volume + budget + période | `2026-06-01_solaire-pme_rhone-alpes` |

Une verticale survit aux campagnes. Une campagne est une instance d'une
verticale sur une zone × volume × période.

## 3. Architecture dossiers

```
verticales/
  solaire-pme-toitures/
    verticale.yaml              # schéma section 4
    templates_sequence/
      mail_j0.md
      mail_j3.md
      mail_j7.md
    pitch_l4.md                 # contexte Claude pour scoring + perso
    README.md                   # 1 paragraphe, à quoi sert cette verticale
  ombrieres-parkings-grandes-surfaces/
    verticale.yaml
    templates_sequence/
    pitch_l4.md
    README.md
  irve-flottes-b2b/
    verticale.yaml
    templates_sequence/
    pitch_l4.md
    README.md

campagnes/
  2026-06-01_solaire-pme_rhone-alpes/
    campagne.yaml               # référence verticale + zone + volume + budget
    data/                       # résultats run (CSV, logs, cache)
```

## 4. Schéma `verticale.yaml`

```yaml
verticale:
  slug: solaire-pme-toitures
  nom: "Panneaux solaires PME — toitures industrielles"
  description: |
    Installateur PV démarchant des PME industrielles et logistiques
    propriétaires de leur bâtiment, avec toiture > 200 m² exploitable.

offre:
  produit: "Centrale PV en autoconsommation ou revente"
  argument_principal: "ROI 6-8 ans, autonomie énergétique, CSRD"
  ticket_moyen_eur: 80000

cibles:
  # Secteurs et requêtes Google Places pour l'étage L1
  secteurs_places:
    - type: "establishment"
      query: "usine agroalimentaire"
    - type: "establishment"
      query: "entrepôt logistique"
    - type: "establishment"
      query: "PME industrielle"

  # Filtres post-L2 pour qualifier les entreprises
  filtres_entreprise:
    effectif_min: 20
    naf_inclus: ["10", "11", "20", "22", "25", "28", "29", "52"]
    naf_exclus: ["56"]
    forme_juridique_inclus: ["SAS", "SARL", "SA"]
    multi_sites_only: false

signaux:
  # Ce qui rend un lead intéressant pour cette verticale
  - "Bâtiment propriétaire (vs locataire)"
  - "Conso élec annuelle estimée > 100 MWh"
  - "Toiture orientée S/SE/SO"
  - "Surface bâti > 500 m²"
  # Note V0 : ces signaux sont décrits en texte libre pour le prompt L4.
  # En V1, ils deviennent calculables (Google Solar API, IGN ortho).

enrichissements:
  l3_5_dropcontact: true     # email vérifié, tél direct, LinkedIn
  lecture_site_web: true     # l'agent lit le site avant de drafter le mail
  detection_terrain: false   # V1 — désactivé en V0

ton_mail:
  registre: "professionnel direct"
  longueur_mots: 120
  attaque: "Constat sur leur conso élec ou leur bâtiment"
  cta: "15 min visio audit gratuit toiture"
  signaux_a_personnaliser:
    - "nom dirigeant"
    - "ville"
    - "secteur précis"
    - "signal lu sur leur site web"

sequence:
  j0:
    template: "templates_sequence/mail_j0.md"
    sujet: "{prenom}, audit toiture {ville} — 15 min ?"
  j3:
    template: "templates_sequence/mail_j3.md"
    sujet: "Relance — {nom_entreprise}"
  j7:
    template: "templates_sequence/mail_j7.md"
    sujet: "Dernière relance — {nom_entreprise}"

budget_typique:
  volume_cible: 200
  cout_pipeline_eur: 15     # L1+L2+L3+L4 Haiku
  cout_avec_l3_5_eur: 45    # + Dropcontact
```

## 5. Les 3 verticales V0 (proposition à confirmer)

| Slug | Offre | Cibles principales | Zone-type | Pourquoi V0 |
|---|---|---|---|---|
| **solaire-pme-toitures** | Panneaux solaires en autoconsommation | PME industrielles, logistique, agro | Région | Pipeline déjà éprouvé sur ce cas |
| **ombrieres-parkings-grandes-surfaces** | Ombrières bois sur parking | Hypers, retail parks, hôpitaux, lycées | National ciblé | Permet de réutiliser config existante Bouches-du-Rhône / Hérault |
| **irve-flottes-b2b** | Bornes IRVE pour flottes entreprise | Entreprises avec flotte VE, concessionnaires | National | Branche sur module veille immat VE existant |

Ces 3 verticales couvrent 3 types de signaux différents (toiture, parking,
flotte) — démontrent la capacité de l'outil à pivoter.

## 6. Création d'une verticale par l'agent

**Canal nominal V0** : l'utilisateur **converse** avec l'agent. L'agent
mène une discovery courte (5-10 échanges max) pour extraire :

1. *Que vends-tu, en une phrase ?*
2. *À qui ? (taille, type d'entreprise, secteur)*
3. *Où ? (national, régional, départemental)*
4. *Qu'est-ce qui rend un prospect particulièrement intéressant ?*
   (signaux : surface, conso, flotte, ancienneté, etc.)
5. *Quel est ton ton de communication ? Un exemple de mail tu trouves bien ?*
6. *Tu as un site web où je peux comprendre ton offre ?* (lu si fourni)

À la fin, l'agent **propose un YAML de verticale** + 3 mails templates.
L'utilisateur amende en conversation jusqu'à validation. Pas de
formulaire rigide.

**Canal expert** : édition `verticales/<slug>/verticale.yaml` directe.

## 7. Pivot inter-verticales

- Streamlit affiche en haut un sélecteur `[Verticale active]`.
- Toutes les commandes (chat agent, lancement campagne, dashboard) sont
  contextualisées par la verticale active.
- Switch = 1 clic, pas de relance d'app.
- Une session de chat agent garde l'historique par verticale.

## 8. B2B en V0, B2C en V1

V0 = **B2B uniquement**. Le pipeline actuel suppose une entreprise avec
SIREN et adresse pro. Adapter au B2C particulier exige :

- Sources données différentes (cadastre DGFiP, listes nominatives achetées)
- RGPD beaucoup plus strict (consentement explicite, pas d'intérêt légitime)
- Pipeline d'enrichissement contact distinct (email perso non scrappable
  proprement)
- Détection terrain souvent requise (toiture maison particulière)

Une verticale dont la cible finale est B2C reste exécutable en V0 via le
prisme B2B : on prospecte les **installateurs / distributeurs / artisans
locaux** qui revendent au particulier. Le B2C direct = V1.

## 9. Champs verticale.yaml — règle d'extension

Tout ajout de champ doit :
1. Avoir un défaut qui ne casse pas les verticales existantes
2. Être documenté dans ce fichier section 4
3. Avoir un test sur au moins 1 verticale d'exemple

Évite l'inflation de champs. Si un champ ne sert qu'à 1 verticale,
préfère un sous-objet `specificites:` libre plutôt qu'un champ
de haut niveau.
