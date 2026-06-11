-- Multi-contacts par lead : sur une PME de 100+ personnes, le bon
-- interlocuteur dépend du discours (DG / DAF / resp. énergie-maintenance).
-- Le contact « principal » reste synchronisé dans leads.contact_* (compat
-- pipeline mail existant) ; son rôle adapte le brouillon.
create table if not exists public.lead_contacts (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid not null references public.leads(id) on delete cascade,
  nom text not null,
  role text,                              -- dg | daf | energie | autre
  email text,
  tel text,
  linkedin text,
  principal boolean not null default false,
  source text not null default 'manuel',  -- manuel | dropcontact
  created_at timestamptz not null default now()
);

create index if not exists lead_contacts_lead_id_idx
  on public.lead_contacts (lead_id);

alter table public.lead_contacts enable row level security;

create policy "lead_contacts_all_auth" on public.lead_contacts
  for all to authenticated using (true) with check (true);

comment on table public.lead_contacts is
  'Interlocuteurs d''un lead. Le principal est recopié dans leads.contact_* ; son rôle pilote le ton du brouillon (DAF → ROI, DG → stratégie/APER, énergie → technique).';
