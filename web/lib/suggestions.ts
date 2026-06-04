// Boucle d'apprentissage (charte point 7 : « une suggestion utile = une
// suggestion suivie »). On referme la boucle ouverte par le traçage des
// suggestion_clicks : les actions recommandées d'un onglet sont RÉORDONNÉES
// selon leur taux de suivi historique (ce qui est cliqué remonte). L'ordre
// d'origine départage les ex æquo, et l'action la plus suivie est marquée.
import type { createClient } from "@/lib/supabase/server";
import type { BandAction } from "@/components/actions-band";

const FENETRE_JOURS = 30;

// Réordonne les actions d'une bande par nombre de clics tracés (source+label),
// sur les 30 derniers jours. Best-effort : en cas d'erreur, ordre d'origine.
export async function rankBandActions(
  supabase: Awaited<ReturnType<typeof createClient>>,
  source: string,
  actions: BandAction[],
): Promise<BandAction[]> {
  const since = new Date(Date.now() - FENETRE_JOURS * 86_400_000).toISOString();
  const { data } = await supabase
    .from("suggestion_clicks")
    .select("action")
    .eq("source", source)
    .gt("at", since)
    .limit(5000);

  const counts: Record<string, number> = {};
  for (const r of (data as { action: string }[] | null) ?? []) {
    counts[r.action] = (counts[r.action] ?? 0) + 1;
  }

  const classees = actions
    .map((a, i) => ({ a, i, c: counts[a.label] ?? 0 }))
    .sort((x, y) => y.c - x.c || x.i - y.i);

  // Marque la plus suivie (si elle a au moins un clic) pour la rendre visible.
  const topClics = classees[0]?.c ?? 0;
  return classees.map((e, rang) => ({
    ...e.a,
    learned: rang === 0 && topClics > 0,
  }));
}
