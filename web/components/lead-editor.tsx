"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { Lead } from "@/lib/database.types";
import {
  forgetLead,
  sendLead,
  setLeadStatus,
  updateLeadEmail,
} from "@/lib/actions/leads";

export function LeadEditor({ lead }: { lead: Lead }) {
  const router = useRouter();
  const [sujet, setSujet] = useState(lead.mail_sujet ?? "");
  const [corps, setCorps] = useState(lead.mail_corps ?? "");
  const [msg, setMsg] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const dirty = sujet !== (lead.mail_sujet ?? "") || corps !== (lead.mail_corps ?? "");

  function run(fn: () => Promise<{ error?: string; ok?: boolean; simulation?: boolean }>, ok: string) {
    setMsg(null);
    startTransition(async () => {
      const res = await fn();
      if (res.error) setMsg(`❌ ${res.error}`);
      else {
        setMsg(res.simulation ? "✅ Envoyé (mode simulation — clé Instantly absente)" : `✅ ${ok}`);
        router.refresh();
      }
    });
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-[var(--border)] bg-white p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
          Email proposé
        </h2>
        <label className="mb-1 block text-xs font-medium text-[var(--muted)]">
          Objet
        </label>
        <input
          value={sujet}
          onChange={(e) => setSujet(e.target.value)}
          className="mb-3 w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
        />
        <label className="mb-1 block text-xs font-medium text-[var(--muted)]">
          Message
        </label>
        <textarea
          value={corps}
          onChange={(e) => setCorps(e.target.value)}
          rows={12}
          className="w-full rounded-lg border border-[var(--border)] px-3 py-2 font-mono text-sm leading-relaxed outline-none focus:border-[var(--brand)]"
        />
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            disabled={pending || !dirty}
            onClick={() => run(() => updateLeadEmail(lead.id, sujet, corps), "Modifications enregistrées")}
            className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-medium hover:bg-slate-50 disabled:opacity-40"
          >
            Enregistrer
          </button>
          <button
            disabled={pending}
            onClick={() => run(() => sendLead(lead.id), "Envoyé")}
            className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--brand-dark)] disabled:opacity-40"
          >
            Envoyer
          </button>
          <button
            disabled={pending}
            onClick={() => run(() => setLeadStatus(lead.id, "ecarte"), "Écarté")}
            className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-medium text-[var(--muted)] hover:bg-slate-50 disabled:opacity-40"
          >
            Écarter
          </button>
          <button
            disabled={pending}
            onClick={() => {
              if (confirm("Effacer les données personnelles de ce prospect (RGPD) ?"))
                run(() => forgetLead(lead.id), "Données effacées");
            }}
            className="ml-auto rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-40"
          >
            Oublier (RGPD)
          </button>
        </div>
        {msg && <p className="mt-3 text-sm">{msg}</p>}
      </div>
    </div>
  );
}
