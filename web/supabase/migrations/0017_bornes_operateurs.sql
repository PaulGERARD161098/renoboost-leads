-- Top opérateurs de bornes (parts de marché) pour l'onglet Bornes VE.
create or replace function public.bornes_stats_operateurs()
returns table(operateur text, n bigint)
language sql
stable
as $$
  select operateur, count(*)::bigint as n
  from public.bornes_recharge
  where operateur is not null and operateur <> ''
  group by operateur
  order by n desc
  limit 20;
$$;

grant execute on function public.bornes_stats_operateurs() to authenticated;
