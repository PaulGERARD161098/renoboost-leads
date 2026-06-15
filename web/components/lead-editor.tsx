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

export function LeadEditor({
  lead,
  angleRecommande,
}: {
  lead: Lead;
  // Reco apprise sur la cible (« privilégie l'angle X ») — propose, non bloquant.
  angleRecommande?: string | null;
}) {
  const router = useRouter();
  const [sujet, setSujet] = useState(lead.mail_sujet ?? "");
  const [corps, setCorps] = useState(lead.mail_corps ?? "");
  const [msg, setMsg] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const [gen, setGen] = useState(false);

  const dirty = sujet !== (lead.mail_sujet ?? "") || corps !== (lead.mail_corps ?? "");

  async function genererBrouillon(mode: "approche" | "relance") {
    setMsg(null);
    setGen(true);
    try {
      const res = await fetch("/api/lead/outreach-draft", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ leadId: lead.id, mode }),
      });
      const data = await res.json();
      if (!res.ok) {
        setMsg(`❌ ${data.error ?? "Génération impossible."}`);
      } else {
        if (data.sujet) setSujet(data.sujet);
        if (data.corps) setCorps(data.corps);
        // Transparence : sur quoi le mail s'appuie-t-il ? (retours terrain : un
        // mail contredisait l'analyse — l'utilisateur doit voir l'angle retenu).
        const angle = data.angle as
          | { pilote: true; label: string; score: number }
          | { pilote: false }
          | undefined;
        const applique = data.angleApplique as { label: string } | null | undefined;
        setMsg(
          angle?.pilote
            ? `✨ Brouillon piloté par l'analyse du site — angle : ${angle.label} (${angle.score}/10). Relis et enregistre ou envoie.`
            : applique
              ? `✨ Brouillon généré — angle ${applique.label} appliqué depuis l'apprentissage (discours qui convertit le mieux sur cette cible, faute d'analyse du site). Relis et enregistre ou envoie.`
              : "✨ Brouillon généré — ⚠️ sans analyse du site (lance l'analyse satellite de la fiche pour un mail piloté par le terrain). Relis et enregistre ou envoie.",
        );
      }
    } catch {
      setMsg("❌ Erreur réseau.");
    } finally {
      setGen(false);
    }
  }

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
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            Email proposé
          </h2>
          <div className="flex gap-1.5">
            <button
              disabled={gen || pending}
              onClick={() => genererBrouillon("approche")}
              title="Magellan rédige un premier email d'approche personnalisé"
              className="rounded-lg border border-[var(--border)] bg-white px-2.5 py-1 text-xs font-medium hover:bg-slate-50 disabled:opacity-40"
            >
              {gen ? "…" : "✨ Brouillon d'approche"}
            </button>
            <button
              disabled={gen || pending}
              onClick={() => genererBrouillon("relance")}
              title="Magellan rédige une relance courte"
              className="rounded-lg border border-[var(--border)] bg-white px-2.5 py-1 text-xs font-medium hover:bg-slate-50 disabled:opacity-40"
            >
              {gen ? "…" : "✨ Relance"}
            </button>
          </div>
        </div>
        {angleRecommande && (
          <p className="mb-3 rounded-lg border border-[var(--brand)]/30 bg-[var(--brand)]/5 px-3 py-2 text-xs text-[var(--text)]">
            💡 {angleRecommande}
          </p>
        )}
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
