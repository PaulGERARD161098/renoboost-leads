"use client";

import { useTransition } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { Lead, LeadStatus } from "@/lib/database.types";
import { scoreColor } from "@/lib/ui";
import { relancerLead, sendLead, setLeadStatus } from "@/lib/actions/leads";

type Action = { label: string; run: () => Promise<{ error?: string }>; primary?: boolean };

export function KanbanCard({ lead }: { lead: Lead }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function go(fn: () => Promise<{ error?: string }>) {
    startTransition(async () => {
      const res = await fn();
      if (!res.error) router.refresh();
    });
  }

  const ecarter: Action = {
    label: "Écarter",
    run: () => setLeadStatus(lead.id, "ecarte"),
  };
  const relancer: Action = { label: "Relancer", run: () => relancerLead(lead.id) };
  const repondu: Action = {
    label: "Répondu",
    run: () => setLeadStatus(lead.id, "repondu"),
  };
  const envoyer: Action = { label: "Envoyer", run: () => sendLead(lead.id), primary: true };

  const ACTIONS: Record<LeadStatus, Action[]> = {
    nouveau: [],
    a_valider: [],
    valide: [envoyer, ecarter],
    envoye: [repondu, relancer],
    ouvert: [repondu, relancer],
    repondu: [ecarter],
    a_relancer: [envoyer, ecarter],
    ecarte: [],
  };

  const actions = ACTIONS[lead.statut] ?? [];

  return (
    <div className="rounded-lg border border-[var(--border)] bg-white p-3 text-sm shadow-sm">
      <Link
        href={`/leads/${lead.id}`}
        className="block font-medium hover:text-[var(--brand)]"
      >
        {lead.entreprise}
      </Link>
      <div className="mt-1 flex items-center justify-between">
        <span className="text-xs text-[var(--muted)]">{lead.ville ?? "—"}</span>
        <span
          className={`rounded px-1.5 py-0.5 text-xs font-semibold ${scoreColor(lead.score)}`}
        >
          {lead.score ?? "—"}
        </span>
      </div>
      {actions.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {actions.map((a) => (
            <button
              key={a.label}
              disabled={pending}
              onClick={() => go(a.run)}
              className={`rounded-md px-2 py-0.5 text-xs font-medium transition disabled:opacity-40 ${
                a.primary
                  ? "bg-[var(--brand)] text-white hover:opacity-90"
                  : "border border-[var(--border)] text-[var(--muted)] hover:bg-slate-50"
              }`}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
