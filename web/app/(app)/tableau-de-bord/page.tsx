import { createClient } from "@/lib/supabase/server";
import type { Lead, Run } from "@/lib/database.types";

export const dynamic = "force-dynamic";

export default async function TableauDeBordPage() {
  const supabase = await createClient();

  const { data: leadsData } = await supabase
    .from("leads")
    .select("score, statut, code_postal, bounced_at")
    .limit(5000);
  const leads =
    (leadsData as Pick<Lead, "score" | "statut" | "code_postal" | "bounced_at">[]) ??
    [];

  const { data: runsData } = await supabase.from("runs").select("status, cout_eur");
  const runs = (runsData as Pick<Run, "status" | "cout_eur">[]) ?? [];

  const total = leads.length;
  const sent = leads.filter((l) =>
    ["envoye", "ouvert", "repondu"].includes(l.statut),
  ).length;
  const opened = leads.filter((l) =>
    ["ouvert", "repondu"].includes(l.statut),
  ).length;
  const replied = leads.filter((l) => l.statut === "repondu").length;
  const bounced = leads.filter((l) => l.bounced_at).length;
  const topLeads = leads.filter((l) => (l.score ?? 0) >= 75).length;
  const coutTotal = runs.reduce((s, r) => s + Number(r.cout_eur ?? 0), 0);

  const pct = (n: number) => (sent ? `${Math.round((n / sent) * 100)}%` : "—");

  // Agrégat par département.
  type Agg = { n: number; somme: number; nbScore: number; top: number; rep: number };
  const parDep: Record<string, Agg> = {};
  for (const l of leads) {
    const dep = l.code_postal ? l.code_postal.slice(0, 2) : "??";
    const a = (parDep[dep] ??= { n: 0, somme: 0, nbScore: 0, top: 0, rep: 0 });
    a.n++;
    if (typeof l.score === "number") {
      a.somme += l.score;
      a.nbScore++;
      if (l.score >= 75) a.top++;
    }
    if (l.statut === "repondu") a.rep++;
  }
  const departements = Object.entries(parDep)
    .map(([dep, a]) => ({
      dep,
      n: a.n,
      score: a.nbScore ? Math.round(a.somme / a.nbScore) : null,
      top: a.top,
      rep: a.rep,
    }))
    .sort((x, y) => y.top - x.top || y.n - x.n)
    .slice(0, 12);

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">Tableau de bord</h1>
      <p className="mb-5 text-sm text-[var(--muted)]">
        Vue d&apos;ensemble de ta prospection.
      </p>

      <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Leads au total" value={total} />
        <Stat label="Top leads (≥75)" value={topLeads} />
        <Stat label="Recherches" value={runs.length} />
        <Stat label="Coût cumulé" value={`${Math.round(coutTotal)} €`} />
      </div>

      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
        Funnel d&apos;envoi
      </h2>
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-5">
        <Stat label="Envoyés" value={sent} />
        <Stat label="Ouverts" value={`${opened} (${pct(opened)})`} />
        <Stat label="Répondus" value={`${replied} (${pct(replied)})`} />
        <Stat label="Rebonds" value={`${bounced} (${pct(bounced)})`} />
        <Stat label="Taux réponse" value={pct(replied)} />
      </div>

      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
        Meilleurs départements
      </h2>
      <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs text-[var(--muted)]">
            <tr>
              <th className="px-4 py-2 font-medium">Dépt</th>
              <th className="px-4 py-2 font-medium">Leads</th>
              <th className="px-4 py-2 font-medium">Score moyen</th>
              <th className="px-4 py-2 font-medium">Top leads</th>
              <th className="px-4 py-2 font-medium">Réponses</th>
            </tr>
          </thead>
          <tbody>
            {departements.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-4 text-[var(--muted)]">
                  Pas encore de données.
                </td>
              </tr>
            ) : (
              departements.map((d) => (
                <tr
                  key={d.dep}
                  className="border-t border-[var(--border)]"
                >
                  <td className="px-4 py-2 font-medium">{d.dep}</td>
                  <td className="px-4 py-2">{d.n}</td>
                  <td className="px-4 py-2">{d.score ?? "—"}</td>
                  <td className="px-4 py-2">{d.top}</td>
                  <td className="px-4 py-2">{d.rep}</td>
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
