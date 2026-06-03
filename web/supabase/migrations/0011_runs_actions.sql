-- Actions sur les recherches (runs) : mode test/démo, renommage/annotation,
-- archivage, appréciation de la moisson. Additif.
alter table public.runs add column if not exists is_test boolean not null default false;
alter table public.runs add column if not exists nom text;
alter table public.runs add column if not exists note text;
alter table public.runs add column if not exists archive boolean not null default false;
alter table public.runs add column if not exists qualite text;

alter table public.runs drop constraint if exists runs_qualite_chk;
alter table public.runs
  add constraint runs_qualite_chk
  check (qualite is null or qualite in ('bonne', 'moyenne', 'mauvaise'));

comment on column public.runs.is_test is
  'Recherche test : traitée en mode démo (faux leads, zéro appel externe) quel que soit WORKER_MODE.';
comment on column public.runs.nom is 'Nom/annotation libre de la recherche.';
comment on column public.runs.archive is 'Recherche archivée : masquée des listes par défaut.';
comment on column public.runs.qualite is 'Appréciation de la moisson : bonne | moyenne | mauvaise.';
