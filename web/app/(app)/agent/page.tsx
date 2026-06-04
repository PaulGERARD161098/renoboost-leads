import { createClient } from "@/lib/supabase/server";
import type {
  AgentConfig,
  AgentJournalEntry,
  Verticale,
} from "@/lib/database.types";
import { AgentConfigForm } from "@/components/agent-config-form";
import { SuggestionValue } from "@/components/suggestion-value";
import { formatDate } from "@/lib/ui";

export const dynamic = "force-dynamic";

const JOURNAL_LABEL: Record<string, string> = {
  run_lance: "🚀 Recherche lancée",
  relance_auto: "🔁 Relances planifiées",
  skip_budget: "⛔ Budget atteint",
  skip_cadence: "⏳ Cadence",
  skip_max: "⛔ Max atteint",
  erreur: "⚠️ Erreur",
  info: "ℹ️ Info",
};

export default async function AgentPage() {
  const supabase = await createClient();

  const { data: cfgData } = await supabase
    .from("agent_config")
    .select("*")
    .order("created_at", { ascending: true })
    .limit(1)
    .maybeSingle();
  const config = cfgData as AgentConfig | null;

  const { data: vData } = await supabase
    .from("verticales")
    .select("id, nom")
    .eq("active", true)
    .order("nom");
  const verticales = (vData as Pick<Verticale, "id" | "nom">[]) ?? [];

  const { data: jData } = await supabase
    .from("agent_journal")
    .select("*")
    .order("at", { ascending: false })
    .limit(15);
  const journal = (jData as AgentJournalEntry[]) ?? [];

  // Budget engagé aujourd'hui.
  const startOfDay = new Date();
  startOfDay.setHours(0, 0, 0, 0);
  const { data: runsToday } = await supabase
    .from("runs")
    .select("budget_eur")
    .gte("created_at", startOfDay.toISOString());
  const engage = ((runsToday as { budget_eur: number | null }[]) ?? []).reduce(
    (s, r) => s + Number(r.budget_eur ?? 0),
    0,
  );

  return (
    <div className="max-w-3xl">
      <h1 className="mb-1 text-2xl font-bold">Agent — Magellan</h1>
      <p className="mb-5 text-sm text-[var(--muted)]">
        Définis le mandat de ton agent. Il prend le relais et lance les
        recherches à ta place, dans ces limites.
      </p>

      {!config ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-white p-8 text-center text-[var(--muted)]">
          Configuration de l&apos;agent indisponible (migration non appliquée ?).
        </div>
      ) : (
        <>
          <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
            <Stat
              label="État"
              value={config.autonomie ? "Autonome" : "En pause"}
            />
            <Stat label="Budget/jour" value={`${config.budget_jour_eur} €`} />
            <Stat
              label="Engagé aujourd'hui"
              value={`${Math.round(engage)} €`}
            />
            <Stat label="Max/jour" value={config.max_runs_jour} />
          </div>

          <AgentConfigForm config={config} verticales={verticales} />

          <div className="mt-8">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
              Journal de l&apos;agent
            </h2>
            <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-white">
              {journal.length === 0 ? (
                <p className="p-4 text-sm text-[var(--muted)]">
                  Rien pour l&apos;instant.
                </p>
              ) : (
                <table className="w-full text-sm">
                  <tbody>
                    {journal.map((j) => (
                      <tr
                        key={j.id}
                        className="border-b border-[var(--border)] last:border-0"
                      >
                        <td className="whitespace-nowrap px-4 py-2 text-[var(--muted)]">
                          {formatDate(j.at)}
                        </td>
                        <td className="whitespace-nowrap px-4 py-2 font-medium">
                          {JOURNAL_LABEL[j.type] ?? j.type}
                        </td>
                        <td className="px-4 py-2 text-[var(--muted)]">
                          {j.message}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </>
      )}

      <SuggestionValue />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-white p-4">
      <div className="text-xl font-bold">{value}</div>
      <div className="text-sm text-[var(--muted)]">{label}</div>
    </div>
  );
}
