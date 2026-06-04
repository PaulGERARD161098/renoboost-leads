-- Traçage des suggestions suivies (charte agent-first point 7 : « mesurer la
-- valeur » — une suggestion utile = une suggestion suivie). Chaque clic sur une
-- action recommandée (bandeau Reprise, modale d'accueil, bande inbox…) est
-- journalisé pour alimenter la boucle d'apprentissage.
create table if not exists public.suggestion_clicks (
  id uuid primary key default gen_random_uuid(),
  source text not null,      -- reprise_banner | welcome_modal | inbox
  action text not null,      -- libellé/clé de l'action suivie
  href text,
  actor uuid references public.profiles(id),
  at timestamptz not null default now()
);
create index if not exists suggestion_clicks_at_idx on public.suggestion_clicks (at desc);

alter table public.suggestion_clicks enable row level security;
create policy "suggestion_clicks_all_auth" on public.suggestion_clicks
  for all to authenticated using (true) with check (true);

comment on table public.suggestion_clicks is
  'Journal des suggestions suivies (clics) — mesure de la valeur des recommandations agent-first.';
