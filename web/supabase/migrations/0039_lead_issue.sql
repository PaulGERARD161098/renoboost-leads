-- Boucle d'apprentissage — la vie d'un lead ne s'arrête plus à « RDV pris » :
-- l'issue est tracée (gagné / perdu + raison), et l'angle du dernier brouillon
-- généré est persisté pour mesurer, plus tard, quel discours convertit.
alter type public.lead_status add value if not exists 'gagne';
alter type public.lead_status add value if not exists 'perdu';

alter table public.leads add column if not exists issue_raison text;
alter table public.leads add column if not exists issue_at timestamptz;
alter table public.leads add column if not exists mail_angle text
  check (mail_angle is null or mail_angle in ('solaire', 'ombrieres', 'bornes'));

comment on column public.leads.issue_raison is
  'Pourquoi gagné/perdu (texte libre saisi à la clôture).';
comment on column public.leads.mail_angle is
  'Axe qui pilotait le dernier brouillon généré (solaire | ombrieres | bornes).';
