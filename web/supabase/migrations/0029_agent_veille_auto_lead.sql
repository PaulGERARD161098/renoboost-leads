-- Incrément D — speed-to-lead : les signaux de veille les plus chauds ne
-- dorment plus dans la file. Quand activé, l'agent convertit automatiquement
-- les signaux dont le score d'intention dépasse le seuil en leads « à valider »
-- et pré-rédige l'approche personnalisée (sous plafond/tick). Aucun envoi.
alter table agent_config
  add column if not exists veille_auto_lead boolean not null default false,
  add column if not exists veille_auto_seuil integer not null default 70;

comment on column agent_config.veille_auto_lead is
  'Convertit automatiquement les signaux de veille chauds en leads (à valider) + pré-rédige l''approche.';
comment on column agent_config.veille_auto_seuil is
  'Score d''intention minimum d''un signal de veille pour la conversion automatique.';
