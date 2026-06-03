import { createClient } from "@/lib/supabase/server";
import { BornesAdmin } from "@/components/bornes-admin";
import { formatDate } from "@/lib/ui";

export const dynamic = "force-dynamic";

async function compte(
  supabase: Awaited<ReturnType<typeof createClient>>,
  source?: string,
): Promise<number> {
  let q = supabase.from("bornes_recharge").select("*", { count: "exact", head: true });
  if (source) q = q.eq("source", source);
  const { count } = await q;
  return count ?? 0;
}

export default async function BornesPage() {
  const supabase = await createClient();
  const [total, irve, rossini] = await Promise.all([
    compte(supabase),
    compte(supabase, "irve"),
    compte(supabase, "rossini"),
  ]);

  const { data: journal } = await supabase
    .from("agent_journal")
    .select("at, message, payload")
    .eq("type", "bornes_ingest")
    .order("at", { ascending: false })
    .limit(1);
  const dernier = journal?.[0] ?? null;

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">Bornes de recharge VE</h1>
      <p className="mb-5 text-sm text-[var(--muted)]">
        Base consolidée (IRVE national + Rossini Energy) pour savoir qui est déjà équipé
        et analyser les territoires.
      </p>

      <div className="mb-5 grid grid-cols-3 gap-3 text-center">
        {[
          ["Total bornes", total],
          ["IRVE (public)", irve],
          ["Rossini Energy", rossini],
        ].map(([label, n]) => (
          <div key={label as string} className="rounded-xl border border-[var(--border)] bg-white p-4">
            <div className="text-2xl font-bold">{(n as number).toLocaleString("fr-FR")}</div>
            <div className="text-xs text-[var(--muted)]">{label as string}</div>
          </div>
        ))}
      </div>

      <div className="mb-5">
        <BornesAdmin />
      </div>

      {dernier && (
        <div className="rounded-xl border border-[var(--border)] bg-white p-5">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            Dernier import — {formatDate(dernier.at)}
          </h2>
          <pre className="max-h-60 overflow-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
            {JSON.stringify(dernier.payload, null, 2)}
          </pre>
        </div>
      )}

      {total === 0 && (
        <p className="mt-4 rounded-xl border border-dashed border-[var(--border)] bg-white p-6 text-center text-sm text-[var(--muted)]">
          Aucune borne chargée pour l’instant. Clique « Importer Rossini » puis « Importer IRVE »
          ci-dessus — le résultat s’affiche aussitôt.
        </p>
      )}
    </div>
  );
}
