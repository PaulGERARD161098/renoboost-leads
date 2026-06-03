import { createClient } from "@/lib/supabase/server";
import { BornesAdmin } from "@/components/bornes-admin";
import { BornesAnalytics } from "@/components/bornes-analytics";
import { BornesRadar } from "@/components/bornes-radar";
import { BornesMapLoader } from "@/components/bornes-map-loader";
import { formatDate } from "@/lib/ui";

export const dynamic = "force-dynamic";

export default async function BornesPage() {
  const supabase = await createClient();

  const { count: total } = await supabase
    .from("bornes_recharge")
    .select("*", { count: "exact", head: true });

  const { data: stats } = await supabase.rpc("bornes_stats_departements");
  const depts = (stats as { departement: string; n: number }[] | null) ?? [];

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
          <BornesRadar depts={depts} />
        </div>
      )}

      <BornesAnalytics depts={depts} />

      {dernier && (
        <p className="mt-4 text-xs text-[var(--muted)]">
          Dernier import : {formatDate(dernier.at)} —{" "}
          {JSON.stringify((dernier.payload as Record<string, unknown>) ?? {})}
        </p>
      )}
    </div>
  );
}
