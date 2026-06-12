-- ════════════════════════════════════════════════════════════════════════
-- SEED DE DÉMO — données réalistes pour faire « briller » les briques agent-first
-- ════════════════════════════════════════════════════════════════════════
-- ⚠️  CE FICHIER N'EST PAS UNE MIGRATION : il n'est PAS appliqué automatiquement.
--     À lancer DÉLIBÉRÉMENT (connecteur Supabase / SQL editor) quand on veut une
--     démo peuplée — carte des tournées, angle gagnant par cible, file d'appels
--     du jour, références chantiers, multi-contacts — sans attendre la vraie data.
--
-- Tout est rattaché au run de démo `is_test = true` ci-dessous et utilise des
-- UUID fixes → ré-exécutable sans doublon (`on conflict do nothing`).
--
-- POUR TOUT EFFACER (rollback démo) :
--   delete from public.lead_contacts where lead_id in
--     (select id from public.leads where run_id = '00000000-0000-0000-0000-0000000000d0');
--   delete from public.leads where run_id = '00000000-0000-0000-0000-0000000000d0';
--   delete from public.runs  where id = '00000000-0000-0000-0000-0000000000d0';
--   delete from public.references_chantiers where id in (
--     '00000000-0000-0000-0000-0000000000r1','00000000-0000-0000-0000-0000000000r2',
--     '00000000-0000-0000-0000-0000000000r3','00000000-0000-0000-0000-0000000000r4');
-- ════════════════════════════════════════════════════════════════════════

-- 1) Run porteur (sentinelle de démo, exclu des stats réelles via is_test).
insert into public.runs (id, status, etape_courante, progress, is_test, nom, note)
values ('00000000-0000-0000-0000-0000000000d0', 'termine', null, 100, true,
        'Démo agent-first', 'Données de démonstration — rollback dans seed_demo.sql')
on conflict (id) do nothing;

-- 2) Leads géolocalisés sur les Hauts-de-France, répartis par cible / angle /
--    statut pour allumer toutes les vues. La cible « Rossini » a assez de signal
--    pour une reco d'angle (bornes 75 % vs ombrières 0 %) ; idem solaire (50 %).
with v as (select id, slug from public.verticales),
d(id, slug, angle, statut, entreprise, siren, naf, libelle_naf, effectif,
  ville, cp, lat, lng, score, score_raison, contact_nom, contact_email,
  contact_tel, sent_days, replied_days, rdv_days, relance_days) as (values
  -- ── Cible ROSSINI (ombrières bois + bornes IRVE) — bornes gagne ───────────
  ('00000000-0000-0000-0000-00000000l001','rossini','bornes','rdv_pris',
   'Transports Delahaye','512345678','4941A','Transports routiers de fret','45 salariés',
   'Lille','59000',50.6292,3.0573,88,'Flotte de 40 utilitaires, dépôt avec parking clôturé — fort potentiel IRVE.',
   'Claire Delahaye','c.delahaye@delahaye-transports.fr','0320001122',12,9,4,null),
  ('00000000-0000-0000-0000-00000000l002','rossini','bornes','repondu',
   'Logipole Nord','523456789','5210B','Entreposage et stockage','60 salariés',
   'Roubaix','59100',50.6942,3.1746,82,'Grand parking poids lourds, demande de recharge nocturne.',
   'Marc Vasseur','m.vasseur@logipole-nord.fr','0320334455',8,3,null,null),
  ('00000000-0000-0000-0000-00000000l003','rossini','bornes','repondu',
   'Garage Central VL','534567890','4520A','Entretien de véhicules','22 salariés',
   'Tourcoing','59200',50.7236,3.1610,76,'Concession multimarque, clientèle VE croissante.',
   'Sophie Bernard','contact@garagecentral-vl.fr','0320556677',6,2,null,null),
  ('00000000-0000-0000-0000-00000000l004','rossini','bornes','envoye',
   'Distri-Frais Métropole','545678901','4631Z','Commerce de gros de légumes','70 salariés',
   'Villeneuve-d''Ascq','59650',50.6200,3.1430,79,'Quai logistique, flotte frigorifique à électrifier.',
   'Hugo Lemaire','h.lemaire@distrifrais.fr','0320667788',4,null,null,null),
  ('00000000-0000-0000-0000-00000000l005','rossini','ombrieres','envoye',
   'Supermarché Vauban','556789012','4711D','Supermarchés','55 salariés',
   'Lens','62300',50.4319,2.8323,71,'Parking client 120 places plein soleil.',
   'Nadia Cherif','direction@super-vauban.fr','0321112233',5,null,null,2),
  ('00000000-0000-0000-0000-00000000l006','rossini','ombrieres','envoye',
   'Jardinerie du Bassin','567890123','4776Z','Commerce de fleurs','30 salariés',
   'Douai','59500',50.3714,3.0800,64,'Vaste parking non ombragé, image éco soignée.',
   'Paul Renard','contact@jardinerie-bassin.fr','0327223344',7,null,null,0),
  -- ── Cible SOLAIRE PME toitures — solaire gagne (50 %) ─────────────────────
  ('00000000-0000-0000-0000-00000000l007','solaire-pme-toitures','solaire','gagne',
   'Menuiserie Lefebvre','578901234','1623Z','Fabrication de charpentes','35 salariés',
   'Valenciennes','59300',50.3590,3.5236,90,'Toiture 1 200 m² plein sud, propriétaire du bâtiment.',
   'Émilie Lefebvre','e.lefebvre@menuiserie-lefebvre.fr','0327334455',20,15,null,null),
  ('00000000-0000-0000-0000-00000000l008','solaire-pme-toitures','solaire','repondu',
   'Plasturgie Arrageoise','589012345','2229A','Fabrication de pièces plastiques','48 salariés',
   'Arras','62000',50.2910,2.7775,84,'Grande halle industrielle, conso élec élevée.',
   'Thomas Petit','t.petit@plast-arras.fr','0321445566',9,2,null,null),
  ('00000000-0000-0000-0000-00000000l009','solaire-pme-toitures','solaire','ouvert',
   'Imprimerie Béthunoise','590123456','1812Z','Autre imprimerie','28 salariés',
   'Béthune','62400',50.5300,2.6400,73,'Toiture plane récente, parc machines énergivore.',
   'Julie Moreau','j.moreau@imprimerie-bethune.fr','0321556677',3,null,null,null),
  ('00000000-0000-0000-0000-00000000l010','solaire-pme-toitures','solaire','envoye',
   'Brasserie des Flandres','601234567','1105Z','Fabrication de bière','40 salariés',
   'Dunkerque','59140',51.0344,2.3768,80,'Bâtiment de production, toiture exploitable importante.',
   'Antoine Dubois','a.dubois@brasserie-flandres.fr','0328667788',4,null,null,null),
  ('00000000-0000-0000-0000-00000000l011','solaire-pme-toitures','bornes','envoye',
   'Carrosserie Cambrésienne','612345678','4520A','Entretien de véhicules','18 salariés',
   'Cambrai','59400',50.1767,3.2350,62,'Atelier avec parking, intérêt borne secondaire.',
   'Lucas Girard','contact@carrosserie-cambrai.fr','0327778899',6,null,null,3),
  -- ── Cible OMBRIÈRES grandes surfaces — pas encore assez de signal (map) ────
  ('00000000-0000-0000-0000-00000000l012','ombrieres-parkings-grandes-surfaces','ombrieres','envoye',
   'Centre Commercial Armentières','623456789','4719A','Grands magasins','120 salariés',
   'Armentières','59280',50.6889,2.8806,77,'Parking 300 places, ERP, forte fréquentation.',
   'Camille Roux','gestion@cc-armentieres.fr','0320889900',5,null,null,null),
  ('00000000-0000-0000-0000-00000000l013','ombrieres-parkings-grandes-surfaces','ombrieres','repondu',
   'Hypermarché Hazebrouck','634567890','4711F','Hypermarchés','150 salariés',
   'Hazebrouck','59190',50.7250,2.5390,81,'Très grand parking, volonté affichée de décarboner.',
   'Olivier Faure','o.faure@hyper-hazebrouck.fr','0328990011',7,3,null,null),
  ('00000000-0000-0000-0000-00000000l014','ombrieres-parkings-grandes-surfaces','ombrieres','nouveau',
   'Retail Park Maubeuge','645678901','4719B','Autres commerces de détail','90 salariés',
   'Maubeuge','59600',50.2787,3.9730,68,'Zone commerciale, parkings vastes — à qualifier.',
   null,null,null,null,null,null,null),
  -- ── Cible IRVE flottes — variété carte ────────────────────────────────────
  ('00000000-0000-0000-0000-00000000l015','irve-flottes-b2b','bornes','envoye',
   'Ambulances Saint-Omer','656789012','8690A','Ambulances','25 salariés',
   'Saint-Omer','62500',50.7500,2.2520,75,'Flotte de 12 véhicules, dépôt avec parking privé.',
   'Sandrine Lacroix','contact@ambulances-stomer.fr','0321001122',5,null,null,1),
  ('00000000-0000-0000-0000-00000000l016','irve-flottes-b2b','bornes','rdv_pris',
   'Taxi Côte d''Opale','667890123','4932Z','Transports de voyageurs par taxis','15 salariés',
   'Calais','62100',50.9513,1.8587,83,'Passage progressif au VE, besoin recharge centralisée.',
   'Yann Leroy','y.leroy@taxi-opale.fr','0321113344',10,6,6,null)
)
insert into public.leads (
  id, run_id, verticale_id, entreprise, siren, naf, libelle_naf, effectif,
  ville, code_postal, latitude, longitude, score, score_raison,
  contact_nom, contact_email, contact_tel, statut, mail_angle,
  sent_at, replied_at, rdv_at, relance_at, hors_filtre)
select
  d.id::uuid, '00000000-0000-0000-0000-0000000000d0'::uuid, v.id,
  d.entreprise, d.siren, d.naf, d.libelle_naf, d.effectif,
  d.ville, d.cp, d.lat, d.lng, d.score, d.score_raison,
  d.contact_nom, d.contact_email, d.contact_tel,
  d.statut::public.lead_status, d.angle,
  case when d.sent_days is not null then now() - (d.sent_days || ' days')::interval end,
  case when d.replied_days is not null then now() - (d.replied_days || ' days')::interval end,
  case when d.rdv_days is not null then now() + (d.rdv_days || ' days')::interval end,
  case when d.relance_days is not null then now() + (d.relance_days || ' days')::interval end,
  false
from d join v on v.slug = d.slug
on conflict (id) do nothing;

-- 3) Références chantiers (preuve sociale géolocalisée) — citées dans les brouillons.
insert into public.references_chantiers (id, nom, ville, lat, lng, axe, description, actif)
values
  ('00000000-0000-0000-0000-0000000000r1','Brasserie du Pavé','Lille',50.6292,3.0573,
   'solaire','Centrale PV 380 kWc en autoconsommation sur toiture industrielle, 2024',true),
  ('00000000-0000-0000-0000-0000000000r2','Hyper Roncq','Roncq',50.7560,3.1390,
   'ombrieres','Ombrières de parking 140 places + 6 bornes IRVE, 2023',true),
  ('00000000-0000-0000-0000-0000000000r3','Transports Vandamme','Lens',50.4319,2.8323,
   'bornes','12 points de charge 22 kW pour flotte utilitaire, 2024',true),
  ('00000000-0000-0000-0000-0000000000r4','Clinique du Hainaut','Valenciennes',50.3590,3.5236,
   'bornes','8 bornes visiteurs + 2 rapides 50 kW, 2025',true)
on conflict (id) do nothing;

-- 4) Multi-contacts par rôle (DG / DAF / énergie) sur deux leads démo.
insert into public.lead_contacts (id, lead_id, nom, role, email, tel, principal, source)
values
  ('00000000-0000-0000-0000-00000000c001','00000000-0000-0000-0000-00000000l001',
   'Claire Delahaye','dg','c.delahaye@delahaye-transports.fr','0320001122',true,'manuel'),
  ('00000000-0000-0000-0000-00000000c002','00000000-0000-0000-0000-00000000l001',
   'Bruno Marchand','daf','b.marchand@delahaye-transports.fr','0320001123',false,'manuel'),
  ('00000000-0000-0000-0000-00000000c003','00000000-0000-0000-0000-00000000l001',
   'Karim Saidi','energie','k.saidi@delahaye-transports.fr','0320001124',false,'dropcontact'),
  ('00000000-0000-0000-0000-00000000c004','00000000-0000-0000-0000-00000000l007',
   'Émilie Lefebvre','dg','e.lefebvre@menuiserie-lefebvre.fr','0327334455',true,'manuel'),
  ('00000000-0000-0000-0000-00000000c005','00000000-0000-0000-0000-00000000l007',
   'Renaud Caron','daf','r.caron@menuiserie-lefebvre.fr','0327334456',false,'manuel')
on conflict (id) do nothing;
