"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { Lead, LeadStatus } from "@/lib/database.types";
import { cloreLead, marquerRdvPris, relancerLead, setLeadStatus } from "@/lib/actions/leads";

export function LeadStatusActions({ lead }: { lead: Lead }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  // Clôture en deux temps : choisir gagné/perdu, puis raison + confirmation.
  const [cloture, setCloture] = useState<"gagne" | "perdu" | null>(null);
  const [raison, setRaison] = useState("");

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
  if ((["envoye", "ouvert", "repondu", "a_relancer"] as LeadStatus[]).includes(s))
    actions.push({ label: "📅 RDV pris", run: () => marquerRdvPris(lead.id) });

  const cloturable = (["rdv_pris", "repondu"] as LeadStatus[]).includes(s);
  if (actions.length === 0 && !cloturable) return null;

  return (
    <div className="mt-3 space-y-2">
      {(actions.length > 0 || cloturable) && (
        <div className="flex flex-wrap gap-2">
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
          {cloturable && (
            <>
              <button
                disabled={pending}
                onClick={() => setCloture(cloture === "gagne" ? null : "gagne")}
                className={`rounded-lg border px-3 py-1.5 text-sm font-medium disabled:opacity-40 ${
                  cloture === "gagne"
                    ? "border-emerald-400 bg-emerald-50 text-emerald-800"
                    : "border-[var(--border)] hover:bg-emerald-50"
                }`}
              >
                🏆 Gagné
              </button>
              <button
                disabled={pending}
                onClick={() => setCloture(cloture === "perdu" ? null : "perdu")}
                className={`rounded-lg border px-3 py-1.5 text-sm font-medium disabled:opacity-40 ${
                  cloture === "perdu"
                    ? "border-rose-400 bg-rose-50 text-rose-700"
                    : "border-[var(--border)] hover:bg-rose-50"
                }`}
              >
                ✖️ Perdu
              </button>
            </>
          )}
        </div>
      )}

      {cloture && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--border)] bg-slate-50 p-2">
          <input
            value={raison}
            onChange={(e) => setRaison(e.target.value)}
            placeholder={
              cloture === "gagne"
                ? "Pourquoi gagné ? (ex. ombrières 40 places, signature Q3)"
                : "Pourquoi perdu ? (ex. budget gelé, parti chez un concurrent)"
            }
            className="min-w-[16rem] flex-1 rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm outline-none focus:border-[var(--brand)]"
          />
          <button
            disabled={pending}
            onClick={() => go(() => cloreLead(lead.id, cloture, raison))}
            className="rounded-lg bg-[var(--brand)] px-3 py-1.5 text-sm font-medium text-white hover:bg-[var(--brand-dark)] disabled:opacity-40"
          >
            Confirmer {cloture === "gagne" ? "🏆" : "✖️"}
          </button>
        </div>
      )}
    </div>
  );
}
