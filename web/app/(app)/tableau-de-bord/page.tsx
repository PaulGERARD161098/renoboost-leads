import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import type { AppContext, Lead, Run } from "@/lib/database.types";
import { RepriseBanner } from "@/components/reprise-banner";
import { CoutDetailBadge } from "@/components/cout-detail";
import { cumulerCoutDetail } from "@/lib/costs";
import { formatDate, satelliteScore100, scoreColor, scoreGlobal } from "@/lib/ui";

export const dynamic = "force-dynamic";

const A_TRAITER = ["nouveau", "a_valider", "valide"];

export default async function TableauDeBordPage() {
  const supabase = await createClient();

  const { data: leadsData } = await supabase
    .from("leads")
    .select(
      "id, entreprise, ville, score, statut, code_postal, bounced_at, relance_at, vision_satellite",
    )
    .limit(5000);
  const leads = (leadsData as Partial<Lead>[]) ?? [];

  const solScore = (l: Partial<Lead>) => satelliteScore100(l.vision_satellite);
  const topSolaire = leads
    .filter((l) => typeof solScore(l) === "number")
    .sort((a, b) => (solScore(b) ?? 0) - (solScore(a) ?? 0))
    .slice(0, 8);
  const fortSolaire = leads.filter((l) => (solScore(l) ?? 0) >= 75).length;

  const endOfDay = new Date();
  endOfDay.setHours(23, 59, 59, 999);
  const relancesDues = leads
    .filter(
      (l) =>
        l.relance_at &&
        new Date(l.relance_at) <= endOfDay &&
        !["ecarte", "repondu"].includes(l.statut ?? ""),
    )
    .sort((a, b) => (a.relance_at! < b.relance_at! ? -1 : 1));

  const { data: runsData } = await supabase
    .from("runs")
    .select("status, cout_eur, cout_detail");
  const runs = (runsData as Pick<Run, "status" | "cout_eur" | "cout_detail">[]) ?? [];

  const { count: veilleNouveaux } = await supabase
    .from("veille_signaux")
    .select("id", { count: "exact", head: true })
    .eq("statut", "nouveau");

  const total = leads.length;
  const sent = leads.filter((l) =>
    ["envoye", "ouvert", "repondu"].includes(l.statut ?? ""),
  ).length;
  const opened = leads.filter((l) =>
    ["ouvert", "repondu"].includes(l.statut ?? ""),
  ).length;
  const replied = leads.filter((l) => l.statut === "repondu").length;
  const bounced = leads.filter((l) => l.bounced_at).length;
  const topLeads = leads.filter((l) => (l.score ?? 0) >= 75).length;
  const coutTotal = runs.reduce((s, r) => s + Number(r.cout_eur ?? 0), 0);
  const coutCumuleDetail = cumulerCoutDetail(runs.map((r) => r.cout_detail));
  const pct = (n: number) => (sent ? Math.round((n / sent) * 100) : 0);

  // À traiter en priorité : non contactés, score décroissant.
  const priorite = leads
    .filter((l) => A_TRAITER.includes(l.statut ?? "") && (l.score ?? 0) > 0)
    .sort((a, b) => (scoreGlobal(b) ?? 0) - (scoreGlobal(a) ?? 0))
    .slice(0, 8);

  // Distribution des scores.
  const band = (min: number, max: number) =>
    leads.filter((l) => (l.score ?? -1) >= min && (l.score ?? -1) <= max).length;
  const distrib = [
    { label: "75-100 (top)", n: band(75, 100), color: "bg-emerald-500" },
    { label: "50-74", n: band(50, 74), color: "bg-amber-500" },
    { label: "0-49", n: band(0, 49), color: "bg-slate-400" },
  ];
  const distribMax = Math.max(1, ...distrib.map((d) => d.n));

  // Meilleurs départements.
  type Agg = { n: number; somme: number; nbScore: number; top: number };
  const parDep: Record<string, Agg> = {};
  for (const l of leads) {
    const dep = l.code_postal ? l.code_postal.slice(0, 2) : "??";
    const a = (parDep[dep] ??= { n: 0, somme: 0, nbScore: 0, top: 0 });
    a.n++;
    if (typeof l.score === "number") {
      a.somme += l.score;
      a.nbScore++;
      if (l.score >= 75) a.top++;
    }
  }
  const departements = Object.entries(parDep)
    .map(([dep, a]) => ({
      dep,
      n: a.n,
      score: a.nbScore ? Math.round(a.somme / a.nbScore) : null,
      top: a.top,
    }))
    .sort((x, y) => y.top - x.top || y.n - x.n)
    .slice(0, 8);

  // Couche contexte (reprise au login) + prochaines actions prioritaires.
  const { data: ctxData } = await supabase
    .from("app_context")
    .select("*")
    .eq("id", "main")
    .maybeSingle();
  const context = (ctxData as AppContext | null) ?? {
    id: "main",
    objectif_final: null,
    client_actif: null,
    deadlines: [],
    resume_session: null,
    resume_genere_le: null,
    calendly_url: null,
    updated_by: null,
    updated_at: new Date().toISOString(),
  };
  const aValider = leads.filter((l) =>
    ["nouveau", "a_valider"].includes(l.statut ?? ""),
  ).length;
  const repriseActions = [
    { label: "Réponses à traiter", href: "/inbox?statut=repondu", n: replied },
    { label: "Leads à valider", href: "/inbox", n: aValider },
    { label: "Relances dues", href: "/suivi", n: relancesDues.length },
  ];

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">Tableau de bord</h1>
      <p className="mb-5 text-sm text-[var(--muted)]">
        Santé du pipeline et prochaines actions.
      </p>

      <RepriseBanner context={context} actions={repriseActions} />

      {(veilleNouveaux ?? 0) > 0 && (
        <Link
          href="/bornes"
          className="mb-5 flex items-center gap-2 rounded-xl border border-[var(--brand)] bg-blue-50/50 px-4 py-3 text-sm font-medium hover:bg-blue-50"
        >
          🔔 {veilleNouveaux} nouveau(x) signal(aux) de veille à examiner
          <span className="text-[var(--brand)]">→</span>
        </Link>
      )}

      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-5">
        <Stat label="Leads au total" value={total} />
        <Stat label="Top leads (≥75)" value={topLeads} />
        <Stat label="Taux de réponse" value={sent ? `${pct(replied)}%` : "—"} />
        <Stat label="Taux de rebond" value={sent ? `${pct(bounced)}%` : "—"} />
        <div className="rounded-xl border border-[var(--border)] bg-white p-4">
          <div className="text-2xl font-bold">
            <CoutDetailBadge
              detail={coutCumuleDetail}
              total={coutTotal}
              totalLabel="Coût cumulé"
            />
          </div>
          <div className="text-sm text-[var(--muted)]">Coût cumulé</div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* À traiter en priorité */}
        <div className="lg:col-span-2">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            🔥 À traiter en priorité
          </h2>
          <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-white">
            {priorite.length === 0 ? (
              <p className="p-4 text-sm text-[var(--muted)]">
                Rien en attente. Lance une recherche pour alimenter le pipeline.
              </p>
            ) : (
              <table className="w-full text-sm">
                <tbody>
                  {priorite.map((l) => (
                    <tr
                      key={l.id}
                      className="border-b border-[var(--border)] last:border-0 hover:bg-slate-50"
                    >
                      <td className="px-4 py-2.5">
                        <Link
                          href={`/leads/${l.id}`}
                          className="font-medium hover:text-[var(--brand)]"
                        >
                          {l.entreprise}
                        </Link>
                      </td>
                      <td className="px-4 py-2.5 text-[var(--muted)]">
                        {l.ville ?? "—"}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <span
                          className={`rounded px-1.5 py-0.5 text-xs font-semibold ${scoreColor(scoreGlobal(l))}`}
                          title="Score global (commercial + foncier)"
                        >
                          {scoreGlobal(l) ?? "—"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Distribution des scores */}
        <div>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            Distribution des scores
          </h2>
          <div className="space-y-3 rounded-xl border border-[var(--border)] bg-white p-4">
            {distrib.map((d) => (
              <div key={d.label}>
                <div className="mb-1 flex justify-between text-xs">
                  <span>{d.label}</span>
                  <span className="font-semibold">{d.n}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className={`h-full ${d.color}`}
                    style={{ width: `${Math.round((d.n / distribMax) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Relances à faire */}
      {relancesDues.length > 0 && (
        <>
          <h2 className="mb-2 mt-8 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            ⏰ Relances à faire ({relancesDues.length})
          </h2>
          <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-white">
            <table className="w-full text-sm">
              <tbody>
                {relancesDues.slice(0, 10).map((l) => (
                  <tr
                    key={l.id}
                    className="border-b border-[var(--border)] last:border-0 hover:bg-slate-50"
                  >
                    <td className="px-4 py-2.5">
                      <Link
                        href={`/leads/${l.id}`}
                        className="font-medium hover:text-[var(--brand)]"
                      >
                        {l.entreprise}
                      </Link>
                    </td>
                    <td className="px-4 py-2.5 text-[var(--muted)]">{l.ville ?? "—"}</td>
                    <td className="px-4 py-2.5 text-right text-xs text-rose-600">
                      {formatDate(l.relance_at ?? null)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Potentiel solaire (satellite) */}
      {topSolaire.length > 0 && (
        <>
          <h2 className="mb-2 mt-8 flex items-center justify-between text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            <span>☀️ Meilleurs potentiels solaires ({fortSolaire} à fort potentiel)</span>
            <Link
              href="/solaire"
              className="font-medium normal-case text-[var(--brand)] hover:underline"
            >
              Ouvrir le workspace Solaire →
            </Link>
          </h2>
          <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-white">
            <table className="w-full text-sm">
              <tbody>
                {topSolaire.map((l) => (
                  <tr
                    key={l.id}
                    className="border-b border-[var(--border)] last:border-0 hover:bg-slate-50"
                  >
                    <td className="px-4 py-2.5">
                      <Link
                        href={`/leads/${l.id}`}
                        className="font-medium hover:text-[var(--brand)]"
                      >
                        {l.entreprise}
                      </Link>
                    </td>
                    <td className="px-4 py-2.5 text-[var(--muted)]">{l.ville ?? "—"}</td>
                    <td className="px-4 py-2.5 text-right">
                      <span
                        className={`rounded px-1.5 py-0.5 text-xs font-semibold ${scoreColor(solScore(l))}`}
                      >
                        ☀️ {solScore(l)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Funnel */}
      <h2 className="mb-2 mt-8 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
        Funnel d&apos;envoi
      </h2>
      <div className="space-y-3 rounded-xl border border-[var(--border)] bg-white p-5">
        <FunnelBar label="Envoyés" n={sent} pct={100} color="bg-indigo-500" />
        <FunnelBar label="Ouverts" n={opened} pct={pct(opened)} color="bg-violet-500" />
        <FunnelBar label="Répondus" n={replied} pct={pct(replied)} color="bg-emerald-500" />
        <FunnelBar label="Rebonds" n={bounced} pct={pct(bounced)} color="bg-rose-400" />
      </div>

      {/* Meilleurs départements */}
      <h2 className="mb-2 mt-8 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
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
            </tr>
          </thead>
          <tbody>
            {departements.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-4 text-[var(--muted)]">
                  Pas encore de données.
                </td>
              </tr>
            ) : (
              departements.map((d) => (
                <tr key={d.dep} className="border-t border-[var(--border)]">
                  <td className="px-4 py-2 font-medium">{d.dep}</td>
                  <td className="px-4 py-2">{d.n}</td>
                  <td className="px-4 py-2">{d.score ?? "—"}</td>
                  <td className="px-4 py-2">{d.top}</td>
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

function FunnelBar({
  label,
  n,
  pct,
  color,
}: {
  label: string;
  n: number;
  pct: number;
  color: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="w-20 shrink-0 text-sm text-[var(--muted)]">{label}</div>
      <div className="h-6 flex-1 overflow-hidden rounded-md bg-slate-100">
        <div
          className={`flex h-full items-center justify-end rounded-md px-2 text-xs font-semibold text-white ${color}`}
          style={{ width: `${Math.max(pct, 6)}%` }}
        >
          {n}
        </div>
      </div>
      <div className="w-12 shrink-0 text-right text-sm font-medium">{pct}%</div>
    </div>
  );
}
