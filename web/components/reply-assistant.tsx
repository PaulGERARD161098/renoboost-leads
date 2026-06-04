"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { LeadReplySuggestion, ReplyCategorie } from "@/lib/database.types";
import { appliquerBrouillonReponse } from "@/lib/actions/leads";

const CAT: Record<ReplyCategorie, { label: string; tone: string }> = {
  interesse: { label: "🟢 Intéressé / veut un RDV", tone: "bg-emerald-100 text-emerald-800" },
  info: { label: "🔵 Demande d'info", tone: "bg-blue-100 text-blue-800" },
  plus_tard: { label: "🟡 Plus tard / pas le moment", tone: "bg-amber-100 text-amber-800" },
  mauvais_interlocuteur: { label: "🟠 Mauvais interlocuteur", tone: "bg-orange-100 text-orange-800" },
  pas_interesse: { label: "🔴 Pas intéressé", tone: "bg-rose-100 text-rose-800" },
  absence: { label: "⚪ Absence / auto-reply", tone: "bg-slate-100 text-slate-600" },
  autre: { label: "⚫ Autre", tone: "bg-slate-100 text-slate-600" },
};

// Magellan — intelligence des réponses : à l'ouverture d'une fiche dont le
// prospect a répondu, classe la réponse + propose un brouillon (Sonnet).
// Propose → l'utilisateur valide (jamais d'envoi auto).
export function ReplyAssistant({ leadId }: { leadId: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sugg, setSugg] = useState<LeadReplySuggestion | null>(null);
  const [sujet, setSujet] = useState("");
  const [corps, setCorps] = useState("");
  const [applying, startApply] = useTransition();
  const [applied, setApplied] = useState(false);

  const charger = useCallback(
    async (force: boolean) => {
      setLoading(true);
      setError(null);
      setApplied(false);
      try {
        const res = await fetch("/api/lead/reply-draft", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ leadId, force }),
        });
        const data = await res.json();
        if (!res.ok) {
          setError(data.error ?? "Génération indisponible.");
          setSugg(null);
        } else {
          const s = data.suggestion as LeadReplySuggestion;
          setSugg(s);
          setSujet(s.sujet ?? "");
          setCorps(s.brouillon);
          setApplied(s.used);
        }
      } catch {
        setError("Réseau indisponible.");
      } finally {
        setLoading(false);
      }
    },
    [leadId],
  );

  useEffect(() => {
    void charger(false);
  }, [charger]);

  function appliquer() {
    if (!sugg) return;
    startApply(async () => {
      const res = await appliquerBrouillonReponse(leadId, sugg.id, sujet, corps);
      if (!res.error) {
        setApplied(true);
        router.refresh();
      } else {
        setError(res.error);
      }
    });
  }

  return (
    <div className="rounded-xl border border-[var(--brand)]/30 bg-gradient-to-br from-[var(--brand)]/5 to-transparent p-5">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
          🧭 Réponse suggérée par Magellan
        </h2>
        <button
          onClick={() => charger(true)}
          disabled={loading || applying}
          className="rounded-lg border border-[var(--border)] bg-white px-2.5 py-1 text-xs font-medium hover:bg-slate-50 disabled:opacity-40"
        >
          ↻ Régénérer
        </button>
      </div>

      {loading ? (
        <p className="text-sm text-[var(--muted)]">Magellan analyse la réponse…</p>
      ) : error ? (
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">{error}</p>
      ) : sugg ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${CAT[sugg.categorie].tone}`}>
              {CAT[sugg.categorie].label}
            </span>
            {sugg.confiance != null && (
              <span className="text-xs text-[var(--muted)]">confiance {sugg.confiance}%</span>
            )}
            {applied && (
              <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">
                ✓ enregistré comme brouillon
              </span>
            )}
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--muted)]">Objet</label>
            <input
              value={sujet}
              onChange={(e) => setSujet(e.target.value)}
              className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--muted)]">Brouillon</label>
            <textarea
              value={corps}
              onChange={(e) => setCorps(e.target.value)}
              rows={8}
              className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm leading-relaxed outline-none focus:border-[var(--brand)]"
            />
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={appliquer}
              disabled={applying || !corps.trim()}
              className="rounded-lg bg-[var(--brand)] px-4 py-1.5 text-sm font-semibold text-white hover:bg-[var(--brand-dark)] disabled:opacity-40"
            >
              {applying ? "Enregistrement…" : "Enregistrer comme brouillon"}
            </button>
            <span className="text-xs text-[var(--muted)]">
              Reprend dans « Email proposé » ci-dessous — rien n'est envoyé.
            </span>
          </div>
        </div>
      ) : null}
    </div>
  );
}
