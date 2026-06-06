-- État de santé global de l'app (signal « voyant » du nom du CRM + bandeau de
-- connexion). Singleton (id='main'). La sévérité combine :
--   • automatique côté app : joignabilité Supabase / navigateur hors-ligne
--     (calculée à la volée, pas stockée ici),
--   • déclarée ici : incident crash / attaque / sécurité posé par un admin ou
--     un futur moniteur — c'est ce qui rend le rouge fiable pour ces cas.
create table if not exists public.system_status (
  id text primary key default 'main',
  severite text not null default 'ok',   -- 'ok' | 'warning' | 'critical'
  message text,                           -- libellé affiché (incident en cours)
  since timestamptz,                      -- depuis quand l'incident est ouvert
  updated_by uuid references public.profiles(id),
  updated_at timestamptz not null default now(),
  constraint system_status_severite_chk check (severite in ('ok', 'warning', 'critical'))
);

insert into public.system_status (id) values ('main') on conflict (id) do nothing;

alter table public.system_status enable row level security;

-- Lecture par TOUS (y compris anon) : la page de connexion, non authentifiée,
-- doit pouvoir afficher un bandeau d'incident.
grant select on public.system_status to anon, authenticated;
create policy "system_status_read_all" on public.system_status
  for select using (true);

-- Écriture réservée aux admins authentifiés (déclarer/lever un incident).
create policy "system_status_write_admin" on public.system_status
  for update to authenticated
  using (exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin'))
  with check (exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin'));

comment on table public.system_status is
  'État de santé global (incident déclaré) : alimente le voyant du nom CRM et le bandeau de la page de connexion.';
