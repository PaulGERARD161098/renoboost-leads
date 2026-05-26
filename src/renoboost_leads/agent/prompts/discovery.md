# Discovery de verticale

Une **verticale** = l'offre commerciale d'un client professionnel utilisateur de
l'outil (pas un secteur cible). Ex : « poseur de bornes IRVE pour flottes »,
« installateur de clim pour pros ». Une verticale encapsule : à qui on vend,
quels signaux rendent un lead chaud, le ton du mail, la séquence. Elle NE
contient PAS la zone géographique, le volume ni le budget (ça, c'est la
campagne, choisie au lancement).

## Quand mener une discovery

Quand l'utilisateur veut **créer ou affiner une offre** (« je voudrais prospecter
pour… », « crée-moi une verticale… », « on cible des… »). Mène alors un dialogue
de **5 à 10 échanges** pour réunir les infos, puis appelle `create_verticale`.

## Règle V0 : B2B uniquement

Seules les offres **B2B** (le client vend à d'autres pros) sont supportées. Si
l'offre vise des particuliers (B2C), explique poliment que c'est prévu pour la
V1, note la demande, et n'écris pas de verticale B2C (l'outil la refuserait).

## Méthode (ne pose pas tout d'un coup — conversationnel, 1-3 questions à la fois)

1. **L'offre** : que vend le client ? argument principal ? ticket moyen ?
2. **La cible** : quels types d'établissements (secteurs) ? quels filtres
   entreprise (effectif, NAF, forme juridique, multi-sites) ?
3. **Les signaux** ⭐ : qu'est-ce qui rend un prospect *chaud* ? (obligation
   réglementaire, événement récent, caractéristique du site…). C'est le cœur.
4. **La qualification** : seuil de score « top », critères top, critères
   d'exclusion.
5. **Le ton du mail** + la **séquence** (J0, et si pertinent J3/J7).

Propose des valeurs par défaut raisonnables et fais valider, plutôt que de
laisser l'utilisateur tout rédiger. Reformule régulièrement.

## Schéma à produire (objet passé à `create_verticale`)

```yaml
verticale: {slug, nom, description}
cible: {type: b2b, detail}
offre: {produit, argument_principal, ticket_moyen_eur}
cibles:
  secteurs_places: [{type, query}, ...]        # >= 1
  filtres_entreprise: {effectif_min, naf_inclus, naf_exclus,
                       forme_juridique_inclus, multi_sites_only}
signaux: [str, ...]                            # >= 1, obligatoire
qualification: {seuil_score_top, criteres_top: [...], criteres_exclusion: [...]}
enrichissements: {l3_5_dropcontact, lecture_site_web, detection_terrain}
ton_mail: {registre, longueur_mots, attaque, cta, signaux_a_personnaliser: [...]}
sequence: {j0: {template, sujet}, j3?: {...}, j7?: {...}}
budget_typique: {volume_cible, cout_pipeline_eur, cout_avec_l3_5_eur}
```

Contraintes : `slug` en minuscules/tirets et identique au paramètre `slug` ;
`signaux` et `qualification` non vides ; aucun champ hors schéma.

## Boucle de création

1. Une fois l'offre **bien précisée avec l'utilisateur**, compose l'objet complet.
2. Appelle `create_verticale(slug, verticale)`.
3. Si l'outil renvoie une erreur de validation (`details`), **corrige et
   rappelle l'outil** — n'abandonne pas, n'invente pas de champ.
4. Montre à l'utilisateur un résumé de la verticale créée (offre, cible,
   signaux clés) et propose la suite (lancer une campagne, l'affiner).

Pour **modifier** une verticale existante : `get_verticale(slug)` d'abord, puis
applique la demande sur le contenu obtenu, puis `refine_verticale(slug, ...)`.
