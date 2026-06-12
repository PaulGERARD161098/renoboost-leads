-- Relances auto — budget journalier visible + pré-rédaction (charte agent-first :
-- propose → l'utilisateur valide → auto SOUS BUDGET/limites).
--
-- Deux garde-fous éditables s'ajoutent au plafond par lead (relance_max) :
--   • relance_auto_max_jour : nombre max de relances PLANIFIÉES par jour, tous
--     leads confondus (budget journalier — borne le rythme global de l'agent) ;
--   • relance_predraft : l'agent rédige aussi le brouillon de relance (jamais
--     envoyé) pour que l'humain n'ait plus qu'à valider/envoyer. Désactivable
--     (économie d'appels IA).
alter table agent_config
  add column if not exists relance_auto_max_jour integer not null default 5,
  add column if not exists relance_predraft boolean not null default true;

comment on column agent_config.relance_auto_max_jour is
  'Budget journalier : relances planifiées max par jour, tous leads confondus.';
comment on column agent_config.relance_predraft is
  'L''agent pré-rédige le brouillon de relance (jamais envoyé) — l''humain valide.';
