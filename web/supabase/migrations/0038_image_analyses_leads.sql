-- Interconnexion analyse d'image → pipeline : mémorise les leads créés depuis
-- une analyse, indexés par la position de l'entreprise dans result.entreprises
-- (map { "<index>": "<lead uuid>" }). Permet à l'UI d'afficher « déjà retenu →
-- ouvrir la fiche » au lieu de recréer un doublon.
alter table public.image_analyses
  add column if not exists leads jsonb not null default '{}'::jsonb;

comment on column public.image_analyses.leads is
  'Leads créés depuis cette analyse : { "<index entreprise dans result>": "<lead uuid>" }.';
