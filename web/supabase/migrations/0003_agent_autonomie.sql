-- Agent autonome (Magellan) : mandat de délégation + journal de traçabilité.
-- Additif.

create table if not exists public.agent_config (
  id uuid primary key default gen_random_uuid(),
  autonomie boolean not null default false,
  cibles_autorisees uuid[] not null default '{}',   -- vide = toutes les cibles actives
  departements text[] not null default '{}',          -- ex {'59','62'}
  budget_jour_eur numeric not null default 20,
  budget_run_eur numeric not null default 15,
  volume_run integer not null default 50,
  effectif_min integer,
  max_runs_jour integer not null default 3,
  cadence_min integer not null default 360,           -- intervalle min entre 2 lancements auto (minutes)
  updated_by uuid references auth.users(id),
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create table if not exists public.agent_journal (
  id uuid primary key default gen_random_uuid(),
  at timestamptz not null default now(),
  type text not null,                                 -- run_lance | skip_budget | skip_cadence | skip_max | info | erreur
  message text,
  run_id uuid references public.runs(id) on delete set null,
  cout_estime_eur numeric,
  payload jsonb not null default '{}'::jsonb
);
create index if not exists agent_journal_at_idx on public.agent_journal (at desc);

alter table public.agent_config enable row level security;
alter table public.agent_journal enable row level security;
create policy "agent_config_all_auth" on public.agent_config
  for all to authenticated using (true) with check (true);
create policy "agent_journal_all_auth" on public.agent_journal
  for all to authenticated using (true) with check (true);

-- Config par défaut si absente (singleton de fait).
insert into public.agent_config (autonomie)
select false
where not exists (select 1 from public.agent_config);
