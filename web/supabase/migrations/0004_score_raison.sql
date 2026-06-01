-- Explicabilité du score : justification textuelle ("pourquoi ce score").
-- Le moteur (étage 4) produit déjà `raison_score` ; on la stocke ici.
-- Additif.
alter table public.leads add column if not exists score_raison text;
