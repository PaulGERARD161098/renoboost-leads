-- Bornes de recharge VE (IRVE + Rossini Energy + Chargemap plus tard) consolidées
-- localement, pour répondre par requête géo : prospect déjà équipé ? voisin ?
-- dans 10 km ? combien par département ? On ingère une fois, on requête localement
-- (pas d'appel externe live). Distances calculées par bounding-box + haversine
-- côté app (lat/lng indexés) — pas de dépendance PostGIS.
create table if not exists public.bornes_recharge (
  id uuid primary key default gen_random_uuid(),
  source text not null default 'irve' check (source in ('irve', 'rossini', 'chargemap')),
  source_id text,                         -- id_pdc_itinerance / id station (clé d'upsert)
  nom_station text,
  operateur text,
  amenageur text,
  enseigne text,
  lat double precision,
  lng double precision,
  puissance_kw numeric,
  nb_points integer,
  adresse text,
  code_postal text,
  commune text,
  departement text,
  date_maj date,
  raw jsonb,
  created_at timestamptz not null default now(),
  unique (source, source_id)
);
create index if not exists bornes_lat_lng_idx on public.bornes_recharge (lat, lng);
create index if not exists bornes_departement_idx on public.bornes_recharge (departement);

alter table public.bornes_recharge enable row level security;
create policy "bornes_read_auth" on public.bornes_recharge
  for select to authenticated using (true);

comment on table public.bornes_recharge is
  'Bornes de recharge VE consolidees (IRVE/Rossini/Chargemap) pour requetes geo : equipe ? voisin ? rayon ? par departement.';
