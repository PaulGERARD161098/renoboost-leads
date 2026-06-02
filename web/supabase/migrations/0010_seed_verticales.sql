-- Seed/sync des verticales : la table `verticales` est une PROJECTION du repo
-- (`verticales/<slug>/verticale.yaml` = source de vérité du ciblage). Le worker
-- `real` charge le fichier PAR SLUG → le slug en base DOIT être le nom de dossier
-- du repo, sinon le run échoue ("Verticale '<slug>' illisible").
--
-- Idempotent : UPDATE de la ligne historique (slug drifté) puis INSERT gardés.
-- Régénéré depuis les fichiers (cf. scripts de sync) — `config` au format CRM
-- {offre, secteurs_naf, effectif_min, signaux} pour l'affichage onglet Cibles.

-- 1) Corrige le slug drifté de la verticale historique (conserve l'id → runs liés).
update verticales
set slug = 'solaire-pme-toitures',
    nom = 'Panneaux solaires PME — toitures industrielles',
    description = 'Installateur PV démarchant des PME industrielles et logistiques propriétaires de leur bâtiment, avec toiture > 200 m² exploitable.',
    config = '{"offre": "Centrale PV en autoconsommation ou revente de surplus", "secteurs_naf": ["10", "11", "20", "22", "25", "28", "29", "52"], "effectif_min": 20, "signaux": ["Bâtiment propriétaire (vs locataire)", "Conso élec annuelle estimée > 100 MWh", "Toiture vaste, plane, orientée S/SE/SO", "Surface bâti > 500 m²"]}'::jsonb,
    updated_at = now()
where slug = 'solaire-toitures-pme';

-- 2) Verticales repo manquantes en base (insérées seulement si absentes).
insert into verticales (slug, nom, description, config, active)
select 'solaire-pme-toitures', 'Panneaux solaires PME — toitures industrielles',
       'Installateur PV démarchant des PME industrielles et logistiques propriétaires de leur bâtiment, avec toiture > 200 m² exploitable.',
       '{"offre": "Centrale PV en autoconsommation ou revente de surplus", "secteurs_naf": ["10", "11", "20", "22", "25", "28", "29", "52"], "effectif_min": 20, "signaux": ["Bâtiment propriétaire (vs locataire)", "Conso élec annuelle estimée > 100 MWh", "Toiture vaste, plane, orientée S/SE/SO", "Surface bâti > 500 m²"]}'::jsonb,
       true
where not exists (select 1 from verticales where slug = 'solaire-pme-toitures');

insert into verticales (slug, nom, description, config, active)
select 'clim-pro-b2b', 'Climatisation réversible — PME tertiaires & commerces',
       'Pose de climatisation réversible pour PME (bureaux, cabinets de santé, commerces et restauration). Argument double saison : rafraîchissement l''été, chauffage performant l''hiver, économies d''énergie.',
       '{"offre": "Installation de climatisation réversible multi-split pour locaux professionnels", "secteurs_naf": ["6820", "6910Z", "6920Z", "7010Z", "7022Z", "7111Z", "7112B", "6201Z", "8621Z", "8622", "8623Z", "8690", "47", "56"], "effectif_min": 10, "signaux": ["Local tertiaire/commerce sans climatisation visible (pas de groupes extérieurs)", "Réversible = besoin double saison : rafraîchir l''été ET chauffer l''hiver", "Rénovation ou aménagement récent des locaux (signal d''investissement)", "Avis Google mentionnant la chaleur, l''inconfort thermique ou l''absence de clim", "Occupant propriétaire de ses locaux (vs bail précaire / location courte durée)", "Épisodes de forte chaleur estivale de plus en plus fréquents (y compris Hauts-de-France)"]}'::jsonb,
       true
where not exists (select 1 from verticales where slug = 'clim-pro-b2b');

insert into verticales (slug, nom, description, config, active)
select 'irve-flottes-b2b', 'Bornes IRVE — flottes entreprise',
       'Installateur IRVE démarchant des entreprises de moyenne taille qui électrifient leur flotte : sociétés dont les ressources sont confirmées (CA), avec immatriculations VE/VHR récentes, cherchant à s''équiper en bornes de recharge sur site.',
       '{"offre": "Infrastructure de recharge VE sur site (bornes + supervision)", "secteurs_naf": ["49", "45", "53", "81", "43"], "effectif_min": 50, "signaux": ["Immatriculations VE/VHR récentes au nom de l''entreprise (données AAA)", "CA annuel confirmé suffisant (ressources) — via Pappers, ou proxy effectif", "Flotte > 10 véhicules", "Parking/dépôt propre pour installer les bornes", "Obligation LOM (flotte > 100 véhicules = quota VE)"]}'::jsonb,
       true
where not exists (select 1 from verticales where slug = 'irve-flottes-b2b');

insert into verticales (slug, nom, description, config, active)
select 'ombrieres-parkings-grandes-surfaces', 'Ombrières de parking — grandes surfaces & ERP',
       'Fabricant/installateur d''ombrières (bois ou acier) démarchant des sites à grand parking exploitable : hypers, retail parks, hôpitaux, cliniques, lycées, salles de séminaire.',
       '{"offre": "Ombrières de parking photovoltaïques + bornes IRVE optionnelles", "secteurs_naf": ["47", "55", "86", "85", "93"], "effectif_min": 50, "signaux": ["Parking extérieur > 3000 m² (estimé satellite/terrain en V1)", "Site opérationnel avec forte fréquentation (avis Google nombreux)", "Obligation décret parkings > 1500 m² (loi APER)", "Propriétaire/exploitant du foncier (vs simple locataire d''une cellule)"]}'::jsonb,
       true
where not exists (select 1 from verticales where slug = 'ombrieres-parkings-grandes-surfaces');

insert into verticales (slug, nom, description, config, active)
select 'rossini', 'Rossini Energy — ombrières bois + bornes IRVE',
       'Installateur d''ombrières solaires en bois imputrescible et de bornes de recharge VE pour des PME B2B (sièges, entrepôts, sites logistiques, industrie). Vend l''installation combinée puis l''entretien.',
       '{"offre": "Ombrières solaires bois + bornes IRVE (installation) + contrat d''entretien", "secteurs_naf": ["10", "20", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33", "49", "52", "53", "70.10"], "effectif_min": 20, "signaux": ["Parking extérieur exploitable — cible ombrières (obligation loi APER dès ~1500 m²)", "Immatriculations VE récentes au nom de l''entreprise (Triple A Data) — signal bornes", "Propriétaire / exploitant du site (vs locataire d''une cellule) — installation possible", "Établissement recevant des travailleurs (ERT), pas du public (ERP)", "Multi-sites (>= 2 établissements) — potentiel de déploiement", "Santé financière solide (CA, résultat net positif) — ressources suffisantes"]}'::jsonb,
       true
where not exists (select 1 from verticales where slug = 'rossini');
