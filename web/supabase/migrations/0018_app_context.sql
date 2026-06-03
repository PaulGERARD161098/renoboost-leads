-- Couche contexte (clé de voûte agent-first) : objectif final, client actif,
-- deadlines, résumé de session → alimente la « reprise au login » du tableau de
-- bord. Singleton (id='main').
create table if not exists public.app_context (
  id text primary key default 'main',
  objectif_final text,
  client_actif text,
  deadlines jsonb not null default '[]'::jsonb,   -- [{ "label": "...", "date": "YYYY-MM-DD" }]
  resume_session text,
  updated_by uuid references public.profiles(id),
  updated_at timestamptz not null default now()
);

insert into public.app_context (id) values ('main') on conflict (id) do nothing;

alter table public.app_context enable row level security;
create policy "app_context_all_auth" on public.app_context
  for all to authenticated using (true) with check (true);

comment on table public.app_context is
  'Couche contexte agent-first : objectif final + client actif + deadlines + résumé de session (reprise au login).';
