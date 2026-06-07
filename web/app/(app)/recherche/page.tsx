import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import type { Lead, Run, Verticale, ZoneCible } from "@/lib/database.types";
import {
  RechercheForm,
  type RechercheInitial,
} from "@/components/recherche-form";
import { RunCard, type RunCounts } from "@/components/run-card";
import { RunActions } from "@/components/run-actions";
import { AutoRefresh } from "@/components/auto-refresh";
import { WorkerStatus } from "@/components/worker-status";
import { KeysPanel } from "@/components/keys-panel";
import { ExplorerMap } from "@/components/explorer-map";
import { RunReportLauncher } from "@/components/run-report";
import { getRunReport } from "@/lib/run-report";

export const dynamic = "force-dynamic";

/** Construit les valeurs de pré-remplissage du formulaire à partir d'un run source. */
function initialFromRun(run: Run): RechercheInitial {
  const zone = run.zone as {
    departement?: string;
    adresse?: string;
    rayon_par_point_km?: number;
    effectif_min?: number;
    effectif_max?: number;
  };
  const isAdresse = !!zone.adresse;
  return {
    verticaleId: run.verticale_id ?? undefined,
    mode: isAdresse ? "adresse" : "departement",
    departement: zone.departement ?? "59",
    adresse: zone.adresse ?? "",
    rayon: zone.rayon_par_point_km ? String(zone.rayon_par_point_km) : "10",
    effectifMin: zone.effectif_min != null ? String(zone.effectif_min) : undefined,
    effectifMax: zone.effectif_max != null ? String(zone.effectif_max) : undefined,
    volume: run.volume_cible != null ? String(run.volume_cible) : "200",
    budget: run.budget_eur != null ? String(run.budget_eur) : "50",
    isTest: run.is_test,
  };
}

export default async function RecherchePage({
  searchParams,
}: {
  searchParams: Promise<{ from?: string; dept?: string }>;
}) {
  const { from, dept } = await searchParams;
  const supabase = await createClient();
  const { data: verticales } = await supabase
    .from("verticales")
    .select("*")
    .eq("active", true)
    .order("nom");
  // Recherches récentes non archivées.
  const { data: runsData } = await supabase
    .from("runs")
    .select("*")
    .eq("archive", false)
    .order("created_at", { ascending: false })
    .limit(10);
  const { data: zonesData } = await supabase
    .from("zones_cibles")
    .select("*")
    .order("created_at", { ascending: false });

  const vlist = (verticales as Verticale[] | null) ?? [];
  const zones = (zonesData as ZoneCible[] | null) ?? [];
  const runs = (runsData as Run[] | null) ?? [];

  // Pré-remplissage si on relance une recherche existante (?from=runId).
  let initial: RechercheInitial | undefined;
  if (from) {
    const { data: src } = await supabase
      .from("runs")
      .select("*")
      .eq("id", from)
      .maybeSingle();
    if (src) initial = initialFromRun(src as Run);
  } else if (dept) {
    // Pré-remplissage depuis « Lancer une recherche ici » (radar Bornes VE).
    initial = {
      mode: "departement",
      departement: dept,
      adresse: "",
      rayon: "10",
      budget: "50",
      isTest: false,
    };
  }

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

  // Rapport de fin de recherche : auto-popup (une fois) quand le run le plus
  // récent vient de se terminer/échouer.
  const dernierTermine = runs.find(
    (r) => r.status === "termine" || r.status === "echoue",
  );
  const autoReport = dernierTermine
    ? await getRunReport(supabase, dernierTermine.id)
    : null;

  return (
    <div>
      <AutoRefresh enabled={!!activeRun} />
      {autoReport && <RunReportLauncher report={autoReport} mode="auto" />}
      <h1 className="mb-1 text-2xl font-bold">Nouvelle recherche</h1>
      <p className="mb-3 text-sm text-[var(--muted)]">
        {initial
          ? "Recherche pré-remplie depuis une recherche existante — ajuste puis relance."
          : "Décris la cible : le moteur trouve et qualifie les prospects."}
      </p>
      {/* État du worker + clés API : une recherche réelle n'aboutit que si le
          worker tourne en mode real avec les clés requises. */}
      <div className="mb-5 space-y-2">
        <WorkerStatus />
        <KeysPanel />
      </div>

      {vlist.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-white p-8 text-center text-[var(--muted)]">
          Aucune cible définie. Crée-en une dans{" "}
          <Link href="/cibles" className="text-[var(--brand)] underline">
            Cibles
          </Link>{" "}
          d&apos;abord.
        </div>
      ) : (
        <RechercheForm verticales={vlist} zones={zones} initial={initial} />
      )}

      {/* 2ᵉ grand badge : explorateur Google Maps satellite + analyse Magellan
          (Vision). La carte reprend toujours le dernier point que tu as exploré. */}
      <section className="mt-6 rounded-2xl border border-[var(--border)] bg-white p-5">
        <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
          <div>
            <h2 className="text-lg font-bold">🗺️ Explorer & analyser une zone</h2>
            <p className="text-sm text-[var(--muted)]">
              Recherche une adresse, balade-toi sur la vue satellite Google Maps,
              puis fais analyser la zone par Magellan (entreprises visibles, terrain,
              opportunités).
            </p>
          </div>
          <Link
            href="/analyse"
            className="rounded-lg border border-[var(--border)] bg-white px-3 py-1.5 text-xs font-medium text-[var(--muted)] transition hover:bg-slate-50"
          >
            📂 Mes analyses →
          </Link>
        </div>
        <ExplorerMap />
      </section>

      {runs.length > 0 && (
        <div className="mt-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            Recherches récentes
          </h2>
          <div className="space-y-3">
            {runs.map((run) => (
              <RunCard
                key={run.id}
                run={run}
                cibleNom={vmap.get(run.verticale_id ?? "") ?? "—"}
                counts={
                  countsByRun.get(run.id) ?? { total: 0, top: 0, horsFiltre: 0 }
                }
                detailHref={`/recherche/${run.id}`}
                actions={<RunActions run={run} />}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
