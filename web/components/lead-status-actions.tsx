"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import type { Lead, LeadStatus } from "@/lib/database.types";
import { relancerLead, setLeadStatus } from "@/lib/actions/leads";

export function LeadStatusActions({ lead }: { lead: Lead }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function go(fn: () => Promise<{ error?: string }>) {
    startTransition(async () => {
      const res = await fn();
      if (!res.error) router.refresh();
    });
  }

  const s = lead.statut;
  const actions: { label: string; run: () => Promise<{ error?: string }> }[] = [];
  if ((["nouveau", "a_valider"] as LeadStatus[]).includes(s))
    actions.push({ label: "Valider", run: () => setLeadStatus(lead.id, "valide") });
  if ((["envoye", "ouvert", "a_relancer"] as LeadStatus[]).includes(s))
    actions.push({ label: "Relancer", run: () => relancerLead(lead.id) });
  if ((["envoye", "ouvert"] as LeadStatus[]).includes(s))
    actions.push({ label: "Marquer répondu", run: () => setLeadStatus(lead.id, "repondu") });

  if (actions.length === 0) return null;

  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {actions.map((a) => (
        <button
          key={a.label}
          disabled={pending}
          onClick={() => go(a.run)}
          className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm font-medium hover:bg-slate-50 disabled:opacity-40"
        >
          {a.label}
        </button>
      ))}
    </div>
  );
}
