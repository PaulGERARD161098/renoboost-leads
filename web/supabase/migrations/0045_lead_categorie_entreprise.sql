-- Catégorie INSEE de l'entreprise (PME / ETI / GE) — « taille de structure ».
-- Alimentée par le worker (stage 2 firmographique) ; sert au résumé de la fiche
-- prospect et au ciblage PME (categorie_entreprise_inclus).
alter table leads
  add column if not exists categorie_entreprise text;

comment on column leads.categorie_entreprise is
  'Catégorie INSEE : PME (<250 sal. & <50 M€), ETI, ou GE. Taille de structure.';
