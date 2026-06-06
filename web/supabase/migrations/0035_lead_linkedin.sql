-- LinkedIn du décideur et de l'entreprise. Ces URLs sont DÉJÀ produites par
-- l'enrichissement Dropcontact (étage 3.5 : linkedin / company_linkedin) mais
-- étaient jusqu'ici jetées au mapping worker. On les propage désormais jusqu'au
-- CRM (fiche prospect + enrichissement on-demand).
alter table public.leads
  add column if not exists contact_linkedin text,
  add column if not exists entreprise_linkedin text;

comment on column public.leads.contact_linkedin is
  'URL du profil LinkedIn du décideur (source : Dropcontact).';
comment on column public.leads.entreprise_linkedin is
  'URL de la page LinkedIn de l''entreprise (source : Dropcontact).';
