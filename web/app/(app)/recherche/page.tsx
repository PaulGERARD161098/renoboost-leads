import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import type { Run, Verticale } from "@/lib/database.types";
import { RechercheForm } from "@/components/recherche-form";
import { RUN_STATUS_LABEL, formatDate } from "@/lib/ui";

export const dynamic = "force-dynamic";

export default async function RecherchePage() {
  const supabase = await createClient();
  const { data: verticales } = await supabase
    .from("verticales")
    .select("*")
    .eq("active", true)
    .order("nom");
  const { data: runs } = await supabase
    .from("runs")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(10);

  const vlist = (verticales as Verticale[] | null) ?? [];

  return (
    <div>
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
        <RechercheForm verticales={vlist} />
      )}

      {runs && runs.length > 0 && (
        <div className="mt-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            Recherches récentes
          </h2>
          <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-white">
            <table className="w-full text-sm">
              <tbody>
                {(runs as Run[]).map((run) => (
                  <tr
                    key={run.id}
                    className="border-b border-[var(--border)] last:border-0 hover:bg-slate-50"
                  >
                    <td className="px-4 py-3">
                      <Link href={`/recherche/${run.id}`} className="block">
                        {formatDate(run.created_at)}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <Link href={`/recherche/${run.id}`} className="block">
                        {(run.zone as { departement?: string })?.departement
                          ? `Dépt ${(run.zone as { departement?: string }).departement}`
                          : "—"}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-[var(--muted)]">
                      <Link href={`/recherche/${run.id}`} className="block">
                        {RUN_STATUS_LABEL[run.status]}
                        {run.status === "en_cours" ? ` · ${run.progress}%` : ""}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
