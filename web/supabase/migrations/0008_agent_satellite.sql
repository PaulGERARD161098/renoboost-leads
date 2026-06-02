-- Option du mandat agent : analyse satellite automatique des leads.
alter table public.agent_config
  add column if not exists satellite_auto boolean not null default false;
