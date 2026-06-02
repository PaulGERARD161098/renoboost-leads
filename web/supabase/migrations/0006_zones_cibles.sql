-- Zones cibles réutilisables (zones d'activité : nom + adresse centrale + rayon).
-- Permet d'enregistrer de bonnes zones et de relancer des recherches autour.
create table if not exists public.zones_cibles (
  id uuid primary key default gen_random_uuid(),
  nom text not null,
  adresse text not null,
  rayon_km numeric not null default 10,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now()
);

alter table public.zones_cibles enable row level security;
create policy "zones_cibles_all_auth" on public.zones_cibles
  for all to authenticated using (true) with check (true);
