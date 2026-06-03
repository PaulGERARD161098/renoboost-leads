import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import type { Lead, LeadStatus, Run, Verticale } from "@/lib/database.types";
import { LEAD_STATUS_LABEL, RUN_STATUS_LABEL, zoneLabel } from "@/lib/ui";
import { LeadsTable } from "@/components/leads-table";
import { RunGroup } from "@/components/run-group";
import { AutoRefresh } from "@/components/auto-refresh";
import type { RunCounts } from "@/components/run-card";

export const dynamic = "force-dynamic";

const TO_PROCESS: LeadStatus[] = ["nouveau", "a_valider", "valide"];

export default async function InboxPage({
  searchParams,
}: {
  searchParams: Promise<{
    statut?: string;
    q?: string;
    vue?: string;
    archives?: string;
  }>;
}) {
  const { statut, q, vue, archives } = await searchParams;
  const search = q?.trim();
  // Les filtres niveau-lead (recherche texte, statut) forcent la vue à plat.
  const flat = vue === "plat" || !!search || !!statut;
  const showArchived = archives === "1";
  const supabase = await createClient();

  if (flat) {
    return (
      <FlatView supabase={supabase} statut={statut} search={search} />
    );
  }

  // Vue groupée par recherche (run) — la plus récente d'abord.
  let runsQuery = supabase
    .from("runs")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(30);
  if (!showArchived) runsQuery = runsQuery.eq("archive", false);
  const { data: runsData } = await runsQuery;
  const runs = (runsData as Run[] | null) ?? [];

  const { data: vData } = await supabase.from("verticales").select("id, nom");
  const vmap = new Map(
    ((vData as Pick<Verticale, "id" | "nom">[] | null) ?? []).map((v) => [
      v.id,
      v.nom,
    ]),
  );

  const leadsByRun = new Map<string, Lead[]>();
  const runIds = runs.map((r) => r.id);
  if (runIds.length > 0) {
    const { data: leadsData } = await supabase
      .from("leads")
      .select("*")
      .in("run_id", runIds)
      .order("score", { ascending: false, nullsFirst: false })
      .limit(2000);
    for (const l of (leadsData as Lead[] | null) ?? []) {
      if (!l.run_id) continue;
      const arr = leadsByRun.get(l.run_id) ?? [];
      arr.push(l);
      leadsByRun.set(l.run_id, arr);
    }
  }

  const activeRun = runs.find(
    (r) => r.status === "en_cours" || r.status === "demande",
  );

  return (
    <div>
      <AutoRefresh enabled={!!activeRun} />

      <div className="mb-5 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold">Prospects</h1>
          <p className="text-sm text-[var(--muted)]">
            Regroupés par recherche — clique une recherche pour dérouler ses
            prospects.
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            href={showArchived ? "/inbox" : "/inbox?archives=1"}
            className={`rounded-lg border px-3 py-1.5 text-sm hover:bg-slate-50 ${
              showArchived
                ? "border-[var(--brand)] bg-blue-50 text-[var(--brand)]"
                : "border-[var(--border)] bg-white text-[var(--muted)]"
            }`}
          >
            {showArchived ? "Masquer archivées" : "Archivées"}
          </Link>
          <Link
            href="/inbox?vue=plat"
            className="rounded-lg border border-[var(--border)] bg-white px-3 py-1.5 text-sm text-[var(--muted)] hover:bg-slate-50"
          >
            Vue à plat
          </Link>
        </div>
      </div>

      {activeRun && (
        <div className="mb-4 rounded-xl border border-blue-200 bg-blue-50 p-3">
          <div className="flex items-center justify-between text-sm text-blue-900">
            <span className="font-medium">
              🔄 Recherche en cours · {vmap.get(activeRun.verticale_id ?? "") ?? "—"}{" "}
              · {zoneLabel(activeRun.zone)}
            </span>
            <span>
              {RUN_STATUS_LABEL[activeRun.status]}
              {activeRun.status === "en_cours" ? ` · ${activeRun.progress}%` : ""}
            </span>
          </div>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-blue-100">
            <div
              className="h-full bg-blue-600 transition-all"
              style={{ width: `${Math.max(4, Math.min(100, activeRun.progress))}%` }}
            />
          </div>
        </div>
      )}

      {runs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-white p-10 text-center text-[var(--muted)]">
          Aucune recherche pour l&apos;instant. Lance-en une depuis{" "}
          <Link href="/recherche" className="text-[var(--brand)] underline">
            Nouvelle recherche
          </Link>
          .
        </div>
      ) : (
        <div className="space-y-3">
          {runs.map((run) => {
            const leads = leadsByRun.get(run.id) ?? [];
            const counts: RunCounts = {
              total: leads.length,
              top: leads.filter((l) => (l.score ?? 0) >= 75).length,
              horsFiltre: leads.filter((l) => l.hors_filtre).length,
            };
            return (
              <RunGroup
                key={run.id}
                run={run}
                cibleNom={vmap.get(run.verticale_id ?? "") ?? "—"}
                counts={counts}
                leads={leads}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

/** Vue à plat historique : table de leads filtrable par statut / texte. */
async function FlatView({
  supabase,
  statut,
  search,
}: {
  supabase: Awaited<ReturnType<typeof createClient>>;
  statut?: string;
  search?: string;
}) {
  let query = supabase
    .from("leads")
    .select("*")
    .order("score", { ascending: false, nullsFirst: false })
    .limit(200);

  if (search) {
    query = query.ilike("entreprise", `%${search}%`);
  } else if (statut && statut in LEAD_STATUS_LABEL) {
    query = query.eq("statut", statut);
  } else {
    query = query.in("statut", TO_PROCESS);
  }

  const { data: leads, error } = await query;

  return (
    <div>
      <div className="mb-5 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold">Prospects</h1>
          <p className="text-sm text-[var(--muted)]">
            {search ? (
              <>
                Résultats pour «&nbsp;{search}&nbsp;» ·{" "}
                <Link href="/inbox" className="text-[var(--brand)] underline">
                  effacer
                </Link>
              </>
            ) : statut ? (
              `Filtre : ${LEAD_STATUS_LABEL[statut as LeadStatus]}`
            ) : (
              "Vue à plat — tous les prospects à traiter, triés par score"
            )}
          </p>
        </div>
        <Link
          href="/inbox"
          className="rounded-lg border border-[var(--border)] bg-white px-3 py-1.5 text-sm text-[var(--muted)] hover:bg-slate-50"
        >
          Par recherche
        </Link>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        <FilterChip label="À traiter" href="/inbox?vue=plat" active={!statut} />
        {(Object.keys(LEAD_STATUS_LABEL) as LeadStatus[]).map((s) => (
          <FilterChip
            key={s}
            label={LEAD_STATUS_LABEL[s]}
            href={`/inbox?statut=${s}`}
            active={statut === s}
          />
        ))}
      </div>

      {error && (
        <p className="rounded-lg bg-red-50 p-4 text-sm text-red-700">
          Erreur de chargement : {error.message}
        </p>
      )}

      {leads && leads.length === 0 && (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-white p-10 text-center text-[var(--muted)]">
          Aucun prospect ici. Lance une recherche depuis{" "}
          <Link href="/recherche" className="text-[var(--brand)] underline">
            Nouvelle recherche
          </Link>
          .
        </div>
      )}

      {leads && leads.length > 0 && <LeadsTable leads={leads as Lead[]} />}
    </div>
  );
}

function FilterChip({
  label,
  href,
  active,
}: {
  label: string;
  href: string;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      className={`rounded-full px-3 py-1 text-xs font-medium transition ${
        active
          ? "bg-[var(--brand)] text-white"
          : "border border-[var(--border)] bg-white text-[var(--muted)] hover:bg-slate-50"
      }`}
    >
      {label}
    </Link>
  );
}
