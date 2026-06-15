-- Garde-fou COÛT des relances auto (porte c) : la pré-rédaction des relances
-- consomme un appel IA par lead. On expose un plafond € journalier éditable —
-- au-delà, l'agent continue de PLANIFIER les relances mais ne pré-rédige plus
-- (l'humain rédige). 0 = pas de plafond de coût.
alter table agent_config
  add column if not exists relance_cout_max_jour numeric(10,2) not null default 0;

comment on column agent_config.relance_cout_max_jour is
  'Plafond € journalier de pré-rédaction des relances (IA). 0 = pas de plafond.';
