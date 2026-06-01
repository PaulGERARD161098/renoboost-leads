-- Migration appliquée au projet Supabase gkvpvuipxyafvbwnqbab (RenoLeads-ICESTREAM)
-- Refonte : interface commerciale "ReSign CRM".
-- ⚠️ Écrase l'ancien schéma (rge_contractors/prospects/outreach_*) — sauvegarde dans backups/.

drop table if exists public.outreach_replies cascade;
drop table if exists public.outreach_messages cascade;
drop table if exists public.prospects cascade;
drop table if exists public.rge_contractors cascade;
drop type if exists public.prospect_status cascade;

create type public.user_role as enum ('admin','commercial');
create type public.run_status as enum ('demande','en_cours','termine','echoue');
create type public.lead_status as enum ('nouveau','a_valider','valide','envoye','ouvert','repondu','a_relancer','ecarte');
create type public.lead_event_type as enum ('cree','envoye','ouvert','repondu','relance','ecarte','note','oubli_rgpd');

create or replace function public.set_updated_at()
returns trigger language plpgsql set search_path = '' as $$
begin new.updated_at = now(); return new; end; $$;

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  nom text,
  role public.user_role not null default 'commercial',
  created_at timestamptz not null default now()
);

create table public.verticales (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,
  nom text not null,
  description text,
  config jsonb not null default '{}'::jsonb,
  active boolean not null default true,
  created_by uuid references public.profiles(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.runs (
  id uuid primary key default gen_random_uuid(),
  verticale_id uuid references public.verticales(id),
  zone jsonb not null default '{}'::jsonb,
  volume_cible integer,
  budget_eur numeric(10,2),
  status public.run_status not null default 'demande',
  etape_courante text,
  progress integer not null default 0 check (progress between 0 and 100),
  counts jsonb not null default '{}'::jsonb,
  cout_eur numeric(10,2) not null default 0,
  log_url text,
  erreur text,
  created_by uuid references public.profiles(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.leads (
  id uuid primary key default gen_random_uuid(),
  run_id uuid references public.runs(id) on delete set null,
  verticale_id uuid references public.verticales(id),
  entreprise text not null,
  siren text, siret text, naf text, libelle_naf text, effectif text,
  ville text, code_postal text,
  score integer check (score between 0 and 100),
  contact_nom text, contact_email text, contact_tel text, site_web text,
  hors_filtre boolean not null default false,
  raison_hors_filtre text,
  mail_sujet text, mail_corps text,
  statut public.lead_status not null default 'nouveau',
  instantly_id text,
  sent_at timestamptz, opened_at timestamptz, replied_at timestamptz,
  owner uuid references public.profiles(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index leads_statut_idx on public.leads(statut);
create index leads_run_idx on public.leads(run_id);
create index leads_score_idx on public.leads(score desc);

create table public.lead_events (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid not null references public.leads(id) on delete cascade,
  type public.lead_event_type not null,
  payload jsonb not null default '{}'::jsonb,
  actor uuid references public.profiles(id),
  at timestamptz not null default now()
);
create index lead_events_lead_idx on public.lead_events(lead_id, at desc);

create trigger trg_verticales_updated before update on public.verticales for each row execute function public.set_updated_at();
create trigger trg_runs_updated before update on public.runs for each row execute function public.set_updated_at();
create trigger trg_leads_updated before update on public.leads for each row execute function public.set_updated_at();

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, email) values (new.id, new.email)
  on conflict (id) do nothing;
  return new;
end; $$;
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users for each row execute function public.handle_new_user();

create or replace function public.is_admin()
returns boolean language sql security definer stable set search_path = public as $$
  select exists(select 1 from public.profiles where id = auth.uid() and role = 'admin');
$$;

alter table public.profiles enable row level security;
alter table public.verticales enable row level security;
alter table public.runs enable row level security;
alter table public.leads enable row level security;
alter table public.lead_events enable row level security;

create policy "profiles_select_auth" on public.profiles for select to authenticated using (true);
create policy "profiles_update_self_or_admin" on public.profiles for update to authenticated
  using (id = auth.uid() or public.is_admin()) with check (id = auth.uid() or public.is_admin());
create policy "verticales_all_auth" on public.verticales for all to authenticated using (true) with check (true);
create policy "runs_all_auth" on public.runs for all to authenticated using (true) with check (true);
create policy "leads_all_auth" on public.leads for all to authenticated using (true) with check (true);
create policy "lead_events_all_auth" on public.lead_events for all to authenticated using (true) with check (true);

alter publication supabase_realtime add table public.runs;
alter publication supabase_realtime add table public.leads;

-- Durcissement : ces fonctions SECURITY DEFINER ne doivent pas être appelables via /rest/v1/rpc.
-- handle_new_user n'est qu'un trigger ; is_admin() ne sert qu'aux policies (rôle authenticated).
revoke execute on function public.handle_new_user() from anon, authenticated, public;
revoke execute on function public.is_admin() from anon, public;
