-- Cold-call inversé (modèle GetYourCall) : on dépose un message vocal sur le
-- numéro du prospect via un numéro dédié (Twilio) ; il nous rappelle. Structure
-- de données + intégration au cycle de vie du lead. La téléphonie réelle (Twilio)
-- est branchée ultérieurement ; ici on pose le modèle. Additif.

-- Numéros dédiés enregistrés (Twilio) servant à déposer/recevoir les appels.
create table if not exists public.phone_numbers (
  id uuid primary key default gen_random_uuid(),
  numero text not null,
  label text,
  provider text not null default 'twilio',
  active boolean not null default true,
  created_at timestamptz not null default now()
);

-- Messages vocaux déposés et rappels associés, pilotables par lead (et campagne).
create table if not exists public.voicemails (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid not null references public.leads(id) on delete cascade,
  campaign_id uuid references public.campaigns(id) on delete set null,
  from_number text,
  to_number text,
  script text,                                  -- texte/scénario du message vocal
  audio_url text,                               -- enregistrement (espace micro) le cas échéant
  statut text not null default 'brouillon'      -- brouillon | planifie | depose | rappel_recu | echec
    check (statut in ('brouillon', 'planifie', 'depose', 'rappel_recu', 'echec')),
  twilio_sid text,
  deposed_at timestamptz,
  callback_at timestamptz,
  created_by uuid references public.profiles(id),
  created_at timestamptz not null default now()
);
create index if not exists voicemails_lead_id_idx on public.voicemails (lead_id, created_at);

-- Statut « canal téléphone » du lead, à côté du canal email, pour la cohérence du pipe.
alter table public.leads add column if not exists call_statut text
  check (call_statut is null or call_statut in
    ('a_appeler', 'message_depose', 'rappel_recu', 'injoignable'));

alter table public.phone_numbers enable row level security;
create policy "phone_numbers_all_auth" on public.phone_numbers
  for all to authenticated using (true) with check (true);
alter table public.voicemails enable row level security;
create policy "voicemails_all_auth" on public.voicemails
  for all to authenticated using (true) with check (true);

comment on table public.voicemails is
  'Cold-call inverse (GetYourCall) : messages vocaux deposes via Twilio + rappels, pilotables par lead.';
comment on column public.leads.call_statut is
  'Statut du canal telephone du lead : a_appeler | message_depose | rappel_recu | injoignable.';
