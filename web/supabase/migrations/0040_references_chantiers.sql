-- Preuve sociale géolocalisée : les chantiers déjà réalisés (références)
-- deviennent citables dans les brouillons — « nous avons équipé X à N km ».
create table if not exists public.references_chantiers (
  id uuid primary key default gen_random_uuid(),
  nom text not null,                     -- client/chantier (ex. « Brasserie du Pavé »)
  ville text,
  lat double precision,
  lng double precision,
  axe text not null check (axe in ('solaire', 'ombrieres', 'bornes')),
  description text,                      -- 1 phrase citable (ex. « 60 places d'ombrières bois, 2024 »)
  actif boolean not null default true,
  created_by uuid references public.profiles(id),
  created_at timestamptz not null default now()
);

alter table public.references_chantiers enable row level security;

create policy "references_all_auth" on public.references_chantiers
  for all to authenticated using (true) with check (true);

comment on table public.references_chantiers is
  'Chantiers de référence (preuve sociale) cités automatiquement dans les brouillons : la plus proche du prospect, sur le même axe.';
