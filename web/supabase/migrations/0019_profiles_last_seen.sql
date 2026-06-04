-- Suivi de la dernière connexion par utilisateur → permet à la modale d'accueil
-- (« reprise au login ») de calculer ce qui est NOUVEAU depuis la dernière
-- session, et de ne s'afficher qu'une fois par jour et par personne.
alter table public.profiles
  add column if not exists last_seen_at timestamptz;

-- Amorce nominative pour la salutation « Bonjour Paul ». Henri : à renseigner
-- dès que son compte est créé (update profiles set nom = 'Henri' where email = …).
update public.profiles
  set nom = 'Paul'
  where email = 'pag.gerard@gmail.com' and (nom is null or nom = '');

comment on column public.profiles.last_seen_at is
  'Horodatage de la dernière session vue (modale d''accueil agent-first).';
