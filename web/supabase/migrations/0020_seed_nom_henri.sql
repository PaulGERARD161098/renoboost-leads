-- Amorce nominative pour la salutation de la modale d'accueil (« Bonjour Henry »).
-- Pendant : Paul est déjà renseigné en 0019.
update public.profiles
  set nom = 'Henry'
  where email = 'henry.huvey@renoboostia.fr' and (nom is null or nom = '');
