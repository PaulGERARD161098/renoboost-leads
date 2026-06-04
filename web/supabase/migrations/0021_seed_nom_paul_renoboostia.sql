-- Identifiant de connexion canonique = l'adresse @renoboostia.fr de chacun.
-- On rattache le prénom au bon compte (Paul sur renoboostia.fr ; Henry est déjà
-- fait en 0020). Le compte Gmail garde son éventuel prénom, sans impact.
update public.profiles
  set nom = 'Paul'
  where email = 'paul.gerard@renoboostia.fr' and (nom is null or nom = '');
