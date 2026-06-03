-- Fil de conversation par lead : messages sortants (nos envois) et entrants
-- (réponses du prospect), pour un rendu type Outlook sur la fiche lead.
-- Complète les colonnes mail_* (dernier brouillon) et lead_events (timeline).
create table if not exists public.lead_messages (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid not null references public.leads(id) on delete cascade,
  direction text not null check (direction in ('out', 'in')),  -- out = nous, in = prospect
  sujet text,
  corps text,
  from_email text,
  to_email text,
  source text not null default 'manuel'                        -- manuel | instantly | systeme
    check (source in ('manuel', 'instantly', 'systeme')),
  instantly_message_id text,
  at timestamptz not null default now()
);
create index if not exists lead_messages_lead_id_at_idx
  on public.lead_messages (lead_id, at);

alter table public.lead_messages enable row level security;
create policy "lead_messages_all_auth" on public.lead_messages
  for all to authenticated using (true) with check (true);

comment on table public.lead_messages is
  'Fil de conversation par lead (envois sortants + réponses entrantes), rendu type Outlook.';
