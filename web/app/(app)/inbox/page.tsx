import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import type { Lead, LeadStatus } from "@/lib/database.types";
import { LEAD_STATUS_COLOR, LEAD_STATUS_LABEL, scoreColor } from "@/lib/ui";

export const dynamic = "force-dynamic";

const TO_PROCESS: LeadStatus[] = ["nouveau", "a_valider", "valide"];

export default async function InboxPage({
  searchParams,
}: {
  searchParams: Promise<{ statut?: string }>;
}) {
  const { statut } = await searchParams;
  const supabase = await createClient();

  let query = supabase
    .from("leads")
    .select("*")
    .order("score", { ascending: false, nullsFirst: false })
    .limit(200);

  if (statut && statut in LEAD_STATUS_LABEL) {
    query = query.eq("statut", statut);
  } else {
    query = query.in("statut", TO_PROCESS);
  }

  const { data: leads, error } = await query;

  return (
    <div>
      <div className="mb-5 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold">Prospects</h1>
          <p className="text-sm text-[var(--muted)]">
            {statut
              ? `Filtre : ${LEAD_STATUS_LABEL[statut as LeadStatus]}`
              : "À traiter — triés par score"}
          </p>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        <FilterChip label="À traiter" href="/inbox" active={!statut} />
        {(Object.keys(LEAD_STATUS_LABEL) as LeadStatus[]).map((s) => (
          <FilterChip
            key={s}
            label={LEAD_STATUS_LABEL[s]}
            href={`/inbox?statut=${s}`}
            active={statut === s}
          />
        ))}
      </div>

      {error && (
        <p className="rounded-lg bg-red-50 p-4 text-sm text-red-700">
          Erreur de chargement : {error.message}
        </p>
      )}

      {leads && leads.length === 0 && (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-white p-10 text-center text-[var(--muted)]">
          Aucun prospect ici. Lance une recherche depuis{" "}
          <Link href="/recherche" className="text-[var(--brand)] underline">
            Nouvelle recherche
          </Link>
          .
        </div>
      )}

      {leads && leads.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-white">
          <table className="w-full text-sm">
            <thead className="border-b border-[var(--border)] bg-slate-50 text-left text-xs uppercase tracking-wide text-[var(--muted)]">
              <tr>
                <th className="px-4 py-3">Entreprise</th>
                <th className="px-4 py-3">Ville</th>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Statut</th>
              </tr>
            </thead>
            <tbody>
              {(leads as Lead[]).map((lead) => (
                <tr
                  key={lead.id}
                  className="border-b border-[var(--border)] last:border-0 hover:bg-slate-50"
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/leads/${lead.id}`}
                      className="font-medium text-[var(--text)] hover:text-[var(--brand)]"
                    >
                      {lead.entreprise}
                    </Link>
                    {lead.libelle_naf && (
                      <div className="text-xs text-[var(--muted)]">
                        {lead.libelle_naf}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-[var(--muted)]">
                    {lead.ville ?? "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block rounded-md px-2 py-0.5 text-xs font-semibold ${scoreColor(lead.score)}`}
                    >
                      {lead.score ?? "—"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${LEAD_STATUS_COLOR[lead.statut]}`}
                    >
                      {LEAD_STATUS_LABEL[lead.statut]}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function FilterChip({
  label,
  href,
  active,
}: {
  label: string;
  href: string;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      className={`rounded-full px-3 py-1 text-xs font-medium transition ${
        active
          ? "bg-[var(--brand)] text-white"
          : "border border-[var(--border)] bg-white text-[var(--muted)] hover:bg-slate-50"
      }`}
    >
      {label}
    </Link>
  );
}
