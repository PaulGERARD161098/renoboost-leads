-- Le worker rapporte la PRÉSENCE (jamais la valeur) des clés API du mode real
-- dans son heartbeat → le panneau « clés » de l'UI sait, sans accès Railway,
-- ce qui est prêt pour la vraie génération.
alter table public.worker_heartbeat
  add column if not exists keys jsonb not null default '{}'::jsonb;

comment on column public.worker_heartbeat.keys is
  'Présence des clés API côté worker (booléens) : { google_places, anthropic, pappers, dropcontact }.';
