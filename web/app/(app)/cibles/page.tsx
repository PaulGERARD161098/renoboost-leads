import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import type { Verticale } from "@/lib/database.types";
import { formatDate } from "@/lib/ui";
import { ReferencesChantiers, type ReferenceRow } from "@/components/references-chantiers";

export const dynamic = "force-dynamic";

export default async function CiblesPage() {
  const supabase = await createClient();
  const { data } = await supabase
    .from("verticales")
    .select("*")
    .order("nom");

  const verticales = (data as Verticale[] | null) ?? [];

  const { data: refsData } = await supabase
    .from("references_chantiers")
    .select("id, nom, ville, lat, axe, description, actif")
    .order("created_at", { ascending: false });
  const refs = (refsData as ReferenceRow[] | null) ?? [];

  return (
    <div>
      <div className="mb-5 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold">Cibles</h1>
          <p className="text-sm text-[var(--muted)]">
            Les profils d&apos;entreprises à prospecter.
          </p>
        </div>
        <Link
          href="/cibles/nouvelle"
          className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--brand-dark)]"
        >
          + Nouvelle cible
        </Link>
      </div>

      {verticales.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-white p-8 text-center text-[var(--muted)]">
          Aucune cible pour l&apos;instant.{" "}
          <Link href="/cibles/nouvelle" className="text-[var(--brand)] underline">
            Créer la première
          </Link>
          .
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {verticales.map((v) => (
            <Link
              key={v.id}
              href={`/cibles/${v.id}`}
              className="block rounded-xl border border-[var(--border)] bg-white p-5 transition hover:border-[var(--brand)]"
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
            </Link>
          ))}
        </div>
      )}

      <ReferencesChantiers refs={refs} />
    </div>
  );
}
