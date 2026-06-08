import { createClient } from "@/lib/supabase/server";
import { BornesAdmin } from "@/components/bornes-admin";
import { BornesAnalytics } from "@/components/bornes-analytics";
import { BornesRadar } from "@/components/bornes-radar";
import { BornesMapLoader } from "@/components/bornes-map-loader";
import { BornesVeille } from "@/components/bornes-veille";
import type { VeilleSignal } from "@/lib/database.types";
import { tallyLeadsParDepartement } from "@/lib/bornes-radar";
import { formatDate } from "@/lib/ui";

export const dynamic = "force-dynamic";

export default async function BornesPage() {
  const supabase = await createClient();

  const { count: total } = await supabase
    .from("bornes_recharge")
    .select("*", { count: "exact", head: true });

  const { data: stats } = await supabase.rpc("bornes_stats_departements");
  const depts = (stats as { departement: string; n: number }[] | null) ?? [];

  // Potentiel pipeline par département : nos prospects déjà localisés (croisé
  // avec le sous-équipement dans le radar). Une seule colonne, requête légère.
  const { data: leadCps } = await supabase
    .from("leads")
    .select("code_postal")
    .not("code_postal", "is", null)
    .limit(20000);
  const leadsParDept = tallyLeadsParDepartement(
    ((leadCps as { code_postal: string | null }[] | null) ?? []).map((l) => l.code_postal),
  );

  const { data: ops } = await supabase.rpc("bornes_stats_operateurs");
  const operateurs = (ops as { operateur: string; n: number }[] | null) ?? [];
  const totalOps = operateurs.reduce((s, o) => s + o.n, 0) || 1;
  const maxOp = operateurs[0]?.n ?? 1;

  const { data: veilleData } = await supabase
    .from("veille_signaux")
    .select("*")
    .in("statut", ["nouveau", "retenu", "converti"])
    .order("created_at", { ascending: false })
    .limit(100);
  const signaux = ((veilleData as VeilleSignal[] | null) ?? []).sort(
    (a, b) =>
      (b.score_intention ?? 0) + (b.score_fit ?? 0) -
      ((a.score_intention ?? 0) + (a.score_fit ?? 0)),
  );

  const { data: journal } = await supabase
    .from("agent_journal")
    .select("at, payload")
    .eq("type", "bornes_ingest")
    .order("at", { ascending: false })
    .limit(1);
  const dernier = journal?.[0] ?? null;

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">Bornes de recharge VE</h1>
      <p className="mb-5 text-sm text-[var(--muted)]">
        Bornes publiques (open-data IRVE national) pour qualifier l’équipement des prospects
        et analyser les territoires. Rossini Energy &amp; Chargemap restent consultables en un
        clic depuis chaque fiche.
      </p>

      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-3">
        <div className="rounded-xl border border-[var(--border)] bg-white p-4 text-center">
          <div className="text-2xl font-bold">{(total ?? 0).toLocaleString("fr-FR")}</div>
          <div className="text-xs text-[var(--muted)]">Bornes IRVE</div>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-white p-4 text-center">
          <div className="text-2xl font-bold">{depts.length}</div>
          <div className="text-xs text-[var(--muted)]">Départements couverts</div>
        </div>
      </div>

      <div className="mb-5">
        <BornesAdmin />
      </div>

      {depts.length > 0 && (
        <div className="mb-5">
          <BornesMapLoader
            counts={Object.fromEntries(depts.map((d) => [d.departement, d.n]))}
          />
        </div>
      )}

      {depts.length > 0 && (
        <div className="mb-5">
          <BornesRadar depts={depts} leadsParDept={leadsParDept} />
        </div>
      )}

      {operateurs.length > 0 && (
        <div className="mb-5 rounded-xl border border-[var(--border)] bg-white p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            🥊 Parts de marché — opérateurs
          </h2>
          <p className="mb-3 text-xs text-[var(--muted)]">
            Qui équipe le marché (national). Repère les acteurs dominants et les angles
            de différenciation.
          </p>
          <ul className="space-y-2">
            {operateurs.map((o) => (
              <li key={o.operateur} className="flex items-center gap-3 text-sm">
                <span className="w-48 shrink-0 truncate" title={o.operateur}>
                  {o.operateur}
                </span>
                <span className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                  <span
                    className="block h-full rounded-full bg-[var(--brand)]"
                    style={{ width: `${(o.n / maxOp) * 100}%` }}
                  />
                </span>
                <span className="w-28 shrink-0 text-right text-[var(--muted)]">
                  {o.n.toLocaleString("fr-FR")} ({((o.n / totalOps) * 100).toFixed(1)} %)
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <BornesAnalytics depts={depts} />

      <div className="mt-5">
        <BornesVeille signaux={signaux} />
      </div>

      {dernier && (
        <p className="mt-4 text-xs text-[var(--muted)]">
          Dernier import : {formatDate(dernier.at)} —{" "}
          {JSON.stringify((dernier.payload as Record<string, unknown>) ?? {})}
        </p>
      )}
    </div>
  );
}
