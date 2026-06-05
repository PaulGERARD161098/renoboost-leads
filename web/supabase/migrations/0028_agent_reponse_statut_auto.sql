-- Incrément C — réponse → statut auto sous garde-fous.
-- Quand activé, la classification d'une réponse applique automatiquement les
-- transitions de statut SÛRES et réversibles (conservateur : seul
-- « plus tard » → planification d'une relance). Les transitions sensibles
-- (écarter sur refus/absence/mauvais interlocuteur) restent proposées en 1 clic.
alter table agent_config
  add column if not exists reponse_statut_auto boolean not null default false;

comment on column agent_config.reponse_statut_auto is
  'Applique automatiquement les transitions de statut sûres déduites de la classification des réponses (conservateur).';
