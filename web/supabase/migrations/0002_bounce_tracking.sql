-- Suivi des rebonds (bounces) email, alimenté par le webhook Instantly.
-- Additif : aucune donnée existante n'est modifiée.

-- Horodatage du rebond sur le lead (null = pas de rebond connu).
alter table public.leads add column if not exists bounced_at timestamptz;

-- Nouvel événement de cycle de vie.
alter type public.lead_event_type add value if not exists 'rebond';

-- Index partiel pour le reporting des bounces.
create index if not exists leads_bounced_idx
  on public.leads (bounced_at)
  where bounced_at is not null;
