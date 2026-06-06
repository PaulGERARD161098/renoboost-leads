-- Affectation d'une campagne à un client : le donneur d'ordre pour le compte
-- duquel la prospection est menée. Sert à brander les mails auto-générés
-- (signature au nom du client plutôt que « L'équipe RénoBoost »). Additif.
alter table public.campaigns
  add column if not exists client_nom text;

comment on column public.campaigns.client_nom is
  'Client (donneur d''ordre) auquel la campagne est affectée. Utilisé pour signer les mails auto-générés en son nom.';
