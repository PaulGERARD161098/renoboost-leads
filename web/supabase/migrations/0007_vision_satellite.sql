-- Vision satellite : adresse + coordonnées du lead, et résultat d'analyse aérienne IGN.
-- Additif.
alter table public.leads add column if not exists adresse text;
alter table public.leads add column if not exists latitude double precision;
alter table public.leads add column if not exists longitude double precision;
alter table public.leads add column if not exists vision_satellite jsonb;
