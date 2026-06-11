-- Téléphone de contact (retour Henry : « mettre un numéro de tél dans les
-- mails ») — inséré sous la signature des brouillons d'approche, de relance
-- et de réponse. Éditable depuis le bandeau Reprise du tableau de bord.
alter table public.app_context add column if not exists telephone text;
comment on column public.app_context.telephone is
  'Téléphone de contact, ajouté sous la signature des emails générés (approche/relance/réponse).';
