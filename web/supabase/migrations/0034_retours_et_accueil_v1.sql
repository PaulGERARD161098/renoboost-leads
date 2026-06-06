-- Lancement V1 — accueil spécial Henry + boucle de retours structurée.
--
-- 1) profiles.welcomed_v1_at : horodate l'accueil « V1 en ligne » pour qu'il ne
--    soit joué qu'UNE seule fois (cinématique de bienvenue d'Henry).
-- 2) table public.retours : file des retours en vrac (Henry via son pop-up, Paul
--    via Magellan). Claude la draine en session, analyse, propose des correctifs
--    en PR draft — aucun changement sans validation de Paul (garde-fou CLAUDE.md).

alter table public.profiles
  add column if not exists welcomed_v1_at timestamptz;

comment on column public.profiles.welcomed_v1_at is
  'Horodatage de l''accueil V1 (cinématique de bienvenue) — jouée une seule fois.';

create table if not exists public.retours (
  id uuid primary key default gen_random_uuid(),
  source text not null,                  -- henry_popup | magellan
  page text,                             -- page d'origine du retour (auto-attachée)
  texte text not null,                   -- le retour en vrac
  statut text not null default 'nouveau',-- nouveau | traite
  created_by uuid references public.profiles(id),
  created_at timestamptz not null default now()
);
create index if not exists retours_statut_idx on public.retours (statut, created_at desc);

alter table public.retours enable row level security;
-- Outil interne 2 personnes (Henry/Paul) : tout authentifié peut écrire/lire.
create policy "retours_all_auth" on public.retours
  for all to authenticated using (true) with check (true);

comment on table public.retours is
  'File des retours utilisateurs (Henry pop-up / Paul via Magellan). Drainée par Claude → correctifs proposés, jamais appliqués sans validation de Paul.';
