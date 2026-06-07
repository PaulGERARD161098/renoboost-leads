-- Ventilation du coût réel d'un run par API, pour un décompte précis des crédits.
-- Le total `cout_eur` reste la source de vérité du coût ; `cout_detail` en donne
-- la répartition par poste : {places, pappers, dropcontact, claude} en €.
-- Alimenté par le worker (worker/pipeline.py → cout_detail_depuis_stats).

alter table runs
  add column if not exists cout_detail jsonb not null default '{}'::jsonb;

comment on column runs.cout_detail is
  'Ventilation du coût réel par API en € : {places, pappers, dropcontact, claude}. Total = cout_eur.';
