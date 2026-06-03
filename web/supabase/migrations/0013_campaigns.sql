-- Campagnes d'emailing : regroupe des leads pour un pilotage global depuis le
-- dashboard (lancement, pause, entonnoir, filtrage). Additif.
create table if not exists public.campaigns (
  id uuid primary key default gen_random_uuid(),
  nom text not null,
  verticale_id uuid references public.verticales(id) on delete set null,
  statut text not null default 'brouillon'                 -- brouillon | active | pausee | terminee
    check (statut in ('brouillon', 'active', 'pausee', 'terminee')),
  note text,
  instantly_campaign_id text,
  created_by uuid references public.profiles(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.leads
  add column if not exists campaign_id uuid references public.campaigns(id) on delete set null;
create index if not exists leads_campaign_id_idx on public.leads (campaign_id);

alter table public.campaigns enable row level security;
create policy "campaigns_all_auth" on public.campaigns
  for all to authenticated using (true) with check (true);

comment on table public.campaigns is
  'Campagnes d''emailing : regroupement de leads pour pilotage global (lancement/pause/entonnoir/filtrage).';
comment on column public.leads.campaign_id is 'Campagne d''emailing à laquelle le lead est rattaché.';
