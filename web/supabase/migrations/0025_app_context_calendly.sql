-- Lien de réservation Calendly, injecté dans les brouillons de réponse quand un
-- prospect est classé « intéressé » (oriente vers la prise de RDV — Palier 3).
alter table public.app_context add column if not exists calendly_url text;
comment on column public.app_context.calendly_url is
  'Lien de réservation Calendly (inséré dans les brouillons de réponse « intéressé »).';
