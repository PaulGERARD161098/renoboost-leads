import Link from "next/link";
import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import type { Lead, Run, Verticale } from "@/lib/database.types";
import { RUN_STATUS_LABEL, LEAD_STATUS_LABEL, scoreColor, formatDate } from "@/lib/ui";
import { RunMapLoader } from "@/components/run-map-loader";
import { RunReportLauncher } from "@/components/run-report";
import { getRunReport } from "@/lib/run-report";

export const dynamic = "force-dynamic";

export default async function RechercheDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createClient();

  const { data: runData } = await supabase
    .from("runs")
    .select("*")
    .eq("id", id)
    .maybeSingle();
  const run = runData as Run | null;
  if (!run) notFound();

  let cibleNom = "—";
  if (run.verticale_id) {
    const { data: v } = await supabase
      .from("verticales")
      .select("nom")
      .eq("id", run.verticale_id)
      .maybeSingle();
    cibleNom = (v as Pick<Verticale, "nom"> | null)?.nom ?? "—";
  }

  const { data: leadsData } = await supabase
    .from("leads")
    .select("id, entreprise, ville, score, statut, contact_email, latitude, longitude")
    .eq("run_id", id)
    .order("score", { ascending: false, nullsFirst: false })
    .limit(500);
  const leads = (leadsData as Partial<Lead>[]) ?? [];

  // Rapport de fin de recherche (coûts, temps, périmètre, entreprises ciblées).
  const report = await getRunReport(supabase, id);

  const zone = run.zone as
    | { departement?: string; adresse?: string; rayon_par_point_km?: number }
    | undefined;
  const mapLeads = leads.map((l) => ({
    id: l.id as string,
    entreprise: (l.entreprise as string) ?? "—",
    ville: l.ville ?? null,
    score: l.score ?? null,
    latitude: l.latitude ?? null,
    longitude: l.longitude ?? null,
  }));
  const hasGeo = mapLeads.some(
    (l) => l.latitude != null && l.longitude != null,
  );
  const showMap = !!zone?.departement || !!zone?.adresse || hasGeo;

  return (
    <div>
      <Link
        href="/recherche"
        className="text-sm text-[var(--muted)] hover:text-[var(--brand)]"
      >
        ← Recherches
      </Link>
      <h1 className="mb-1 mt-2 text-2xl font-bold">
        {cibleNom}
        {zone?.departement ? ` · Dépt ${zone.departement}` : ""}
      </h1>
      <p className="mb-3 text-sm text-[var(--muted)]">
        {formatDate(run.created_at)} · {RUN_STATUS_LABEL[run.status]}
        {run.status === "en_cours" ? ` · ${run.progress}%` : ""}
      </p>
      {report && (
        <div className="mb-5">
          <RunReportLauncher report={report} />
        </div>
      )}

      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Résultats" value={leads.length} />
        <Stat label="Volume visé" value={run.volume_cible ?? "—"} />
        <Stat label="Budget" value={run.budget_eur ? `${run.budget_eur} €` : "—"} />
        <Stat label="Coût réel" value={`${Math.round(Number(run.cout_eur ?? 0))} €`} />
      </div>

      {showMap && (
        <div className="mb-6">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            Carte de la zone
          </h2>
          <RunMapLoader
            departement={zone?.departement ?? null}
            adresse={zone?.adresse ?? null}
            rayonKm={zone?.rayon_par_point_km ?? null}
            leads={mapLeads}
          />
          {!hasGeo && (
            <p className="mt-2 text-xs text-[var(--muted)]">
              Zone affichée ; les prospects n&apos;ont pas encore de
              géolocalisation (drapeaux indisponibles).
            </p>
          )}
        </div>
      )}

      {run.erreur && (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {run.erreur}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs text-[var(--muted)]">
            <tr>
              <th className="px-4 py-2 font-medium">Entreprise</th>
              <th className="px-4 py-2 font-medium">Ville</th>
              <th className="px-4 py-2 font-medium">Statut</th>
              <th className="px-4 py-2 font-medium">Score</th>
            </tr>
          </thead>
          <tbody>
            {leads.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-4 text-[var(--muted)]">
                  Pas encore de résultats — la recherche est probablement en cours.
                </td>
              </tr>
            ) : (
              leads.map((l) => (
                <tr key={l.id} className="border-t border-[var(--border)]">
                  <td className="px-4 py-2">
                    <Link
                      href={`/leads/${l.id}`}
                      className="font-medium hover:text-[var(--brand)]"
                    >
                      {l.entreprise}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-[var(--muted)]">{l.ville ?? "—"}</td>
                  <td className="px-4 py-2 text-[var(--muted)]">
                    {l.statut ? (LEAD_STATUS_LABEL[l.statut] ?? l.statut) : "—"}
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`rounded px-1.5 py-0.5 text-xs font-semibold ${scoreColor(l.score ?? null)}`}
                    >
                      {l.score ?? "—"}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-white p-4">
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-sm text-[var(--muted)]">{label}</div>
    </div>
  );
}
