-- Veille d'intentions : signaux web détectés par l'agent (VE flotte, ombrières,
-- électrification, IRVE) sur le périmètre des cibles. Orienté capture de leads.
create table if not exists public.veille_signaux (
  id uuid primary key default gen_random_uuid(),
  entreprise text not null,
  ville text,
  type text,                              -- ve_flotte | ombrieres | electrification | irve | autre
  declencheur text,                       -- le "pourquoi maintenant" (événement daté)
  resume text,
  source_url text,
  source_date text,
  score_intention integer,                -- 0-100 : force du signal d'intention
  score_fit integer,                      -- 0-100 : adéquation avec nos offres
  angle text,                             -- accroche de prise de contact recommandée
  statut text not null default 'nouveau', -- nouveau | retenu | ecarte | converti
  lead_id uuid references public.leads(id) on delete set null,
  created_at timestamptz not null default now()
);
create index if not exists veille_signaux_statut_idx
  on public.veille_signaux (statut, created_at desc);

alter table public.veille_signaux enable row level security;
create policy "veille_signaux_all_auth" on public.veille_signaux
  for all to authenticated using (true) with check (true);
