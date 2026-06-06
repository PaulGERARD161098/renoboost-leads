-- Analyses d'images (captures Google Maps satellite + uploads manuels) par
-- Magellan (Claude Vision) : extrait entreprises, terrain, opportunités
-- commerciales. Historique persistant + image stockée dans Supabase Storage
-- (bucket privé `analyses`, scopée par utilisateur).

create table if not exists public.image_analyses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.profiles(id) on delete set null,
  source text not null check (source in ('upload', 'capture')),
  label text,
  address text,
  lat double precision,
  lng double precision,
  zoom integer,
  image_path text not null,
  result jsonb not null default '{}'::jsonb,
  cout_eur numeric default 0,
  created_at timestamptz not null default now()
);

create index if not exists image_analyses_user_created_idx
  on public.image_analyses (user_id, created_at desc);

alter table public.image_analyses enable row level security;

create policy "image_analyses_select_own" on public.image_analyses
  for select to authenticated
  using (user_id = auth.uid() or user_id is null);

create policy "image_analyses_insert_self" on public.image_analyses
  for insert to authenticated
  with check (user_id = auth.uid());

create policy "image_analyses_delete_own" on public.image_analyses
  for delete to authenticated
  using (user_id = auth.uid());

comment on table public.image_analyses is
  'Historique des analyses Magellan Vision sur captures GMaps satellite ou uploads manuels.';
comment on column public.image_analyses.image_path is
  'Chemin de l''image dans le bucket Storage `analyses` (format <user_id>/<uuid>.png).';
comment on column public.image_analyses.result is
  'Résultat structuré : {entreprises[], terrain{...}, opportunites[], accroche, texte}.';

-- Bucket Storage privé pour les images capturées/uploadées.
insert into storage.buckets (id, name, public)
values ('analyses', 'analyses', false)
on conflict (id) do nothing;

-- Politiques Storage : un utilisateur gère uniquement les fichiers de son dossier
-- (la convention de chemin est <auth.uid()>/<uuid>.png).
drop policy if exists "analyses_select_own" on storage.objects;
create policy "analyses_select_own" on storage.objects
  for select to authenticated
  using (
    bucket_id = 'analyses'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

drop policy if exists "analyses_insert_own" on storage.objects;
create policy "analyses_insert_own" on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'analyses'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

drop policy if exists "analyses_delete_own" on storage.objects;
create policy "analyses_delete_own" on storage.objects
  for delete to authenticated
  using (
    bucket_id = 'analyses'
    and (storage.foldername(name))[1] = auth.uid()::text
  );
