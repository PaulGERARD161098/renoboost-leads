-- Date/heure du rendez-vous pris (PR3 — calendrier RDV).
-- Capté via le webhook Calendly (scheduled_event.start_time) ou renseigné à la
-- main. Permet un vrai calendrier daté, en complément du statut `rdv_pris`.
-- Additif, sans impact sur l'existant.
alter table public.leads add column if not exists rdv_at timestamptz;
create index if not exists leads_rdv_at_idx
  on public.leads (rdv_at)
  where rdv_at is not null;
