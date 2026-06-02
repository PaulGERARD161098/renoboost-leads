-- Rappels / relances datées : date de prochaine relance planifiée sur un lead.
-- Additif.
alter table public.leads add column if not exists relance_at timestamptz;
create index if not exists leads_relance_idx
  on public.leads (relance_at)
  where relance_at is not null;
