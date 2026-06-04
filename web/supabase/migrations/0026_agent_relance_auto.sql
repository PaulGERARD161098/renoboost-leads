-- Palier 3.1 — Relances automatiques sous garde-fous.
-- L'agent détecte les envois restés sans réponse et PLANIFIE la relance
-- (statut a_relancer + relance_at) sans jamais envoyer : la worklist se remplit,
-- l'humain valide et envoie. Garde-fous éditables dans l'onglet Agent.
alter table agent_config
  add column if not exists relance_auto boolean not null default false,
  add column if not exists relance_delai_jours integer not null default 5,
  add column if not exists relance_max integer not null default 2;

comment on column agent_config.relance_auto is
  'Active la planification automatique des relances (détection sans envoi).';
comment on column agent_config.relance_delai_jours is
  'Jours de silence après le dernier envoi avant de proposer une relance.';
comment on column agent_config.relance_max is
  'Nombre maximum de relances automatiques par lead (garde-fou anti-harcèlement).';
