"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { Voicemail, VoicemailStatus } from "@/lib/database.types";

const VM_STATUT_LABEL: Record<VoicemailStatus, string> = {
  brouillon: "Brouillon",
  planifie: "Planifié",
  depose: "Déposé",
  rappel_recu: "Rappel reçu",
  echec: "Échec",
};
const VM_STATUT_COLOR: Record<VoicemailStatus, string> = {
  brouillon: "bg-slate-100 text-slate-600",
  planifie: "bg-blue-100 text-blue-700",
  depose: "bg-indigo-100 text-indigo-700",
  rappel_recu: "bg-green-100 text-green-800",
  echec: "bg-red-100 text-red-700",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Cold-call inversé (GetYourCall), pilotable par lead. STUB télécom : l'espace
// micro et l'envoi réel Twilio seront branchés ; ici on pose le pilotage.
export function ColdCallPanel({
  leadId,
  initial,
  configured,
  hasPhone,
}: {
  leadId: string;
  initial: Voicemail[];
  configured: boolean;
  hasPhone: boolean;
}) {
  const router = useRouter();
  const [script, setScript] = useState("");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function deposer() {
    setLoading(true);
    setMsg(null);
    try {
      const res = await fetch("/api/twilio/voicemail", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ leadId, script }),
      });
      const data = await res.json();
      if (data.error) setMsg(data.error);
      else {
        setScript("");
        setMsg(
          data.configured
            ? "Message déposé."
            : "Message planifié (Twilio à brancher pour le dépôt réel).",
        );
        router.refresh();
      }
    } catch {
      setMsg("Connexion impossible. Réessaie.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-[var(--border)] bg-white p-5">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
          Cold-call inversé (messagerie vocale)
        </h2>
        {!configured && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
            Twilio à brancher
          </span>
        )}
      </div>

      {!hasPhone ? (
        <p className="text-sm text-[var(--muted)]">
          Aucun numéro de téléphone sur ce lead — renseigne-le pour pouvoir déposer un
          message vocal.
        </p>
      ) : (
        <>
          <textarea
            value={script}
            onChange={(e) => setScript(e.target.value)}
            placeholder="Script du message vocal à déposer (le prospect rappellera notre numéro dédié)…"
            rows={3}
            className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
          />
          <div className="mt-2 flex items-center gap-2">
            <button
              type="button"
              disabled
              title="Enregistrement vocal — bientôt"
              className="cursor-not-allowed rounded-lg border border-dashed border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--muted)]"
            >
              🎙️ Enregistrer (bientôt)
            </button>
            <button
              type="button"
              onClick={deposer}
              disabled={loading}
              className="rounded-lg bg-[var(--brand)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
            >
              {loading ? "Dépôt…" : "Déposer le message"}
            </button>
            {msg && <span className="text-xs text-[var(--muted)]">{msg}</span>}
          </div>
        </>
      )}

      {initial.length > 0 && (
        <ul className="mt-4 space-y-2 border-t border-[var(--border)] pt-3 text-sm">
          {initial.map((vm) => (
            <li key={vm.id} className="flex items-center justify-between gap-2">
              <span className="truncate text-[var(--muted)]">
                {vm.script ? vm.script : "(sans script)"}
              </span>
              <span className="flex shrink-0 items-center gap-2">
                <span className="text-xs text-[var(--muted)]">
                  {formatDate(vm.callback_at ?? vm.deposed_at ?? vm.created_at)}
                </span>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${VM_STATUT_COLOR[vm.statut]}`}
                >
                  {VM_STATUT_LABEL[vm.statut]}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
