import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import type { Lead, LeadStatus } from "@/lib/database.types";
import { LEAD_STATUS_LABEL } from "@/lib/ui";
import { LeadsTable } from "@/components/leads-table";

export const dynamic = "force-dynamic";

const TO_PROCESS: LeadStatus[] = ["nouveau", "a_valider", "valide"];

export default async function InboxPage({
  searchParams,
}: {
  searchParams: Promise<{ statut?: string; q?: string }>;
}) {
  const { statut, q } = await searchParams;
  const search = q?.trim();
  const supabase = await createClient();

  let query = supabase
    .from("leads")
    .select("*")
    .order("score", { ascending: false, nullsFirst: false })
    .limit(200);

  if (search) {
    query = query.ilike("entreprise", `%${search}%`);
  } else if (statut && statut in LEAD_STATUS_LABEL) {
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
            {search ? (
              <>
                Résultats pour «&nbsp;{search}&nbsp;» ·{" "}
                <Link href="/inbox" className="text-[var(--brand)] underline">
                  effacer
                </Link>
              </>
            ) : statut ? (
              `Filtre : ${LEAD_STATUS_LABEL[statut as LeadStatus]}`
            ) : (
              "À traiter — triés par score"
            )}
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

      {leads && leads.length > 0 && <LeadsTable leads={leads as Lead[]} />}
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
