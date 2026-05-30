import { createClient } from "@/lib/supabase/server";
import type { Verticale } from "@/lib/database.types";
import { formatDate } from "@/lib/ui";

export const dynamic = "force-dynamic";

export default async function CiblesPage() {
  const supabase = await createClient();
  const { data } = await supabase
    .from("verticales")
    .select("*")
    .order("nom");

  const verticales = (data as Verticale[] | null) ?? [];

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">Cibles</h1>
      <p className="mb-5 text-sm text-[var(--muted)]">
        Les profils d&apos;entreprises à prospecter. L&apos;éditeur guidé arrive
        au prochain jalon.
      </p>

      {verticales.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-white p-8 text-center text-[var(--muted)]">
          Aucune cible pour l&apos;instant.
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {verticales.map((v) => (
            <div
              key={v.id}
              className="rounded-xl border border-[var(--border)] bg-white p-5"
            >
              <div className="flex items-start justify-between">
                <h2 className="font-semibold">{v.nom}</h2>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    v.active
                      ? "bg-emerald-100 text-emerald-800"
                      : "bg-slate-200 text-slate-500"
                  }`}
                >
                  {v.active ? "Active" : "Inactive"}
                </span>
              </div>
              {v.description && (
                <p className="mt-2 text-sm text-[var(--muted)]">
                  {v.description}
                </p>
              )}
              <p className="mt-3 text-xs text-[var(--muted)]">
                Modifiée le {formatDate(v.updated_at)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
