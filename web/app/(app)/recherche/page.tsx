import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import type { Lead, Run, Verticale, ZoneCible } from "@/lib/database.types";
import { RechercheForm } from "@/components/recherche-form";
import { RunCard, type RunCounts } from "@/components/run-card";
import { AutoRefresh } from "@/components/auto-refresh";

export const dynamic = "force-dynamic";

export default async function RecherchePage() {
  const supabase = await createClient();
  const { data: verticales } = await supabase
    .from("verticales")
    .select("*")
    .eq("active", true)
    .order("nom");
  const { data: runsData } = await supabase
    .from("runs")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(10);
  const { data: zonesData } = await supabase
    .from("zones_cibles")
    .select("*")
    .order("created_at", { ascending: false });

  const vlist = (verticales as Verticale[] | null) ?? [];
  const zones = (zonesData as ZoneCible[] | null) ?? [];
  const runs = (runsData as Run[] | null) ?? [];

  // Compteurs par recherche + nom de cible (pour les cartouches).
  const vmap = new Map(vlist.map((v) => [v.id, v.nom]));
  const countsByRun = new Map<string, RunCounts>();
  const runIds = runs.map((r) => r.id);
  if (runIds.length > 0) {
    const { data: leadsData } = await supabase
      .from("leads")
      .select("run_id, score, hors_filtre")
      .in("run_id", runIds)
      .limit(5000);
    for (const l of (leadsData as Pick<Lead, "run_id" | "score" | "hors_filtre">[] | null) ?? []) {
      if (!l.run_id) continue;
      const c = countsByRun.get(l.run_id) ?? { total: 0, top: 0, horsFiltre: 0 };
      c.total += 1;
      if ((l.score ?? 0) >= 75) c.top += 1;
      if (l.hors_filtre) c.horsFiltre += 1;
      countsByRun.set(l.run_id, c);
    }
  }
  const activeRun = runs.find(
    (r) => r.status === "en_cours" || r.status === "demande",
  );

  return (
    <div>
      <AutoRefresh enabled={!!activeRun} />
      <h1 className="mb-1 text-2xl font-bold">Nouvelle recherche</h1>
      <p className="mb-5 text-sm text-[var(--muted)]">
        Décris la cible : le moteur trouve et qualifie les prospects.
      </p>

      {vlist.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-white p-8 text-center text-[var(--muted)]">
          Aucune cible définie. Crée-en une dans{" "}
          <Link href="/cibles" className="text-[var(--brand)] underline">
            Cibles
          </Link>{" "}
          d&apos;abord.
        </div>
      ) : (
        <RechercheForm verticales={vlist} zones={zones} />
      )}

      {runs.length > 0 && (
        <div className="mt-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            Recherches récentes
          </h2>
          <div className="space-y-3">
            {runs.map((run) => (
              <Link key={run.id} href={`/recherche/${run.id}`} className="block">
                <RunCard
                  run={run}
                  cibleNom={vmap.get(run.verticale_id ?? "") ?? "—"}
                  counts={
                    countsByRun.get(run.id) ?? { total: 0, top: 0, horsFiltre: 0 }
                  }
                />
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
