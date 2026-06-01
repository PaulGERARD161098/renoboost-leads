import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import type { Lead, LeadStatus } from "@/lib/database.types";
import { scoreColor } from "@/lib/ui";

export const dynamic = "force-dynamic";

const COLUMNS: { statut: LeadStatus; label: string }[] = [
  { statut: "valide", label: "À envoyer" },
  { statut: "envoye", label: "Envoyés" },
  { statut: "ouvert", label: "Ouverts" },
  { statut: "repondu", label: "Répondus" },
  { statut: "a_relancer", label: "À relancer" },
];

export default async function SuiviPage() {
  const supabase = await createClient();
  const { data } = await supabase
    .from("leads")
    .select("*")
    .order("score", { ascending: false, nullsFirst: false })
    .limit(500);

  const leads = (data as Lead[] | null) ?? [];
  const byStatus = (s: LeadStatus) => leads.filter((l) => l.statut === s);

  const sent = leads.filter((l) =>
    ["envoye", "ouvert", "repondu"].includes(l.statut),
  ).length;
  const opened = leads.filter((l) =>
    ["ouvert", "repondu"].includes(l.statut),
  ).length;
  const replied = byStatus("repondu").length;

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">Suivi</h1>
      <p className="mb-5 text-sm text-[var(--muted)]">
        Pipeline d&apos;envoi et de réponses.
      </p>

      <div className="mb-6 grid grid-cols-3 gap-4">
        <Stat label="Envoyés" value={sent} />
        <Stat
          label="Taux d'ouverture"
          value={sent ? `${Math.round((opened / sent) * 100)}%` : "—"}
        />
        <Stat
          label="Taux de réponse"
          value={sent ? `${Math.round((replied / sent) * 100)}%` : "—"}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-5">
        {COLUMNS.map((col) => {
          const items = byStatus(col.statut);
          return (
            <div key={col.statut} className="rounded-xl bg-slate-100/60 p-3">
              <div className="mb-2 flex items-center justify-between px-1">
                <h2 className="text-sm font-semibold">{col.label}</h2>
                <span className="text-xs text-[var(--muted)]">
                  {items.length}
                </span>
              </div>
              <div className="space-y-2">
                {items.map((lead) => (
                  <Link
                    key={lead.id}
                    href={`/leads/${lead.id}`}
                    className="block rounded-lg border border-[var(--border)] bg-white p-3 text-sm shadow-sm hover:border-[var(--brand)]"
                  >
                    <div className="font-medium">{lead.entreprise}</div>
                    <div className="mt-1 flex items-center justify-between">
                      <span className="text-xs text-[var(--muted)]">
                        {lead.ville ?? "—"}
                      </span>
                      <span
                        className={`rounded px-1.5 py-0.5 text-xs font-semibold ${scoreColor(lead.score)}`}
                      >
                        {lead.score ?? "—"}
                      </span>
                    </div>
                  </Link>
                ))}
                {items.length === 0 && (
                  <p className="px-1 py-3 text-xs text-[var(--muted)]">Vide</p>
                )}
              </div>
            </div>
          );
        })}
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
