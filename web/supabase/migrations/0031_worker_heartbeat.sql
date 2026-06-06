-- Observabilité du worker M3 (charte agent-first : « voir le worker vivant sans
-- passer par un dev »). Le worker écrit son battement de cœur à chaque poll ;
-- l'UI lit la fraîcheur de last_seen_at pour savoir si le process tourne, son
-- mode (demo/real), la version déployée et le nombre de runs en file.
-- Singleton (id='main'), à l'image de app_context.
create table if not exists public.worker_heartbeat (
  id text primary key default 'main',
  last_seen_at timestamptz,
  mode text,                                  -- 'demo' | 'real'
  version text,                               -- SHA court du build déployé (Railway)
  pending_runs integer not null default 0,    -- runs 'demande' vus au dernier poll
  last_error text,                            -- dernier échec de run (tronqué)
  last_error_at timestamptz,
  updated_at timestamptz not null default now()
);

insert into public.worker_heartbeat (id) values ('main') on conflict (id) do nothing;

alter table public.worker_heartbeat enable row level security;

-- Lecture seule pour l'UI authentifiée ; l'écriture passe par le worker en
-- service_role (qui contourne RLS) — l'app ne doit jamais falsifier un heartbeat.
create policy "worker_heartbeat_read_auth" on public.worker_heartbeat
  for select to authenticated using (true);

comment on table public.worker_heartbeat is
  'Battement de cœur du worker M3 : liveness + mode + version + runs en file (observabilité UI).';
