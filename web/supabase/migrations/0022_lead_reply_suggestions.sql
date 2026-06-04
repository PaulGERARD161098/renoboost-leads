-- Suggestions de réponse Magellan (Palier 2 « intelligence des réponses ») :
-- pour chaque message entrant d'un prospect, on cache la classification + le
-- brouillon généré (Sonnet) afin de ne pas recalculer à chaque ouverture de
-- fiche, et on trace si la suggestion est SUIVIE (used) — mesure de la valeur.
create table if not exists public.lead_reply_suggestions (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid not null references public.leads(id) on delete cascade,
  in_message_id uuid references public.lead_messages(id) on delete cascade,
  categorie text not null,                       -- interesse | info | plus_tard | mauvais_interlocuteur | pas_interesse | absence | autre
  confiance integer,                             -- 0-100
  sujet text,
  brouillon text not null,
  used boolean not null default false,           -- la suggestion a-t-elle été enregistrée comme brouillon ?
  created_at timestamptz not null default now()
);
-- Une seule suggestion par message entrant (clé du get-or-generate).
create unique index if not exists lead_reply_suggestions_msg_uidx
  on public.lead_reply_suggestions (in_message_id);

alter table public.lead_reply_suggestions enable row level security;
create policy "lead_reply_suggestions_all_auth" on public.lead_reply_suggestions
  for all to authenticated using (true) with check (true);

comment on table public.lead_reply_suggestions is
  'Cache des suggestions de réponse Magellan (classification + brouillon) par message entrant, avec traçage de l''usage.';
