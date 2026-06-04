-- Résumé de session auto-généré (boucle reprise au login) : on horodate la
-- dernière génération du récap pour ne pas le recalculer inutilement (1×/jour).
alter table public.app_context
  add column if not exists resume_genere_le timestamptz;

comment on column public.app_context.resume_genere_le is
  'Dernière génération auto du résumé de session (récap « où on en est »).';
