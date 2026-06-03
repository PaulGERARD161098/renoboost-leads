-- Agrégation des bornes par département (pour la page d'analyses /bornes).
create or replace function public.bornes_stats_departements()
returns table(departement text, n bigint)
language sql
stable
as $$
  select departement, count(*)::bigint as n
  from public.bornes_recharge
  where departement is not null
  group by departement
  order by n desc;
$$;

grant execute on function public.bornes_stats_departements() to authenticated;
