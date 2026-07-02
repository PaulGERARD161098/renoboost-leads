"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { VeilleSignal } from "@/lib/database.types";
import { retenirSignal, ecarterSignal } from "@/lib/actions/veille";

const TYPE_LABEL: Record<string, string> = {
  ve_flotte: "🚐 Flotte VE",
  irve: "🔌 Bornes IRVE",
  ombrieres: "🅿️ Ombrières",
  electrification: "⚡ Électrification",
  autre: "📌 Signal",
};

export function VeilleList({ signaux }: { signaux: VeilleSignal[] }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  async function lancer() {
    setLoading(true);
    setMsg(null);
    try {
      const res = await fetch("/api/veille/run", { method: "POST" });
      const data = await res.json();
      if (data.error) setMsg(`❌ ${data.error}`);
      else setMsg(`✅ ${data.inserted ?? 0} nouveau(x) signal(aux).`);
      router.refresh();
    } catch {
      setMsg("❌ Connexion impossible.");
    } finally {
      setLoading(false);
    }
  }

  function act(fn: () => Promise<{ error?: string }>) {
    setMsg(null);
    startTransition(async () => {
      const res = await fn();
      if (res.error) setMsg(`❌ ${res.error}`);
      else router.refresh();
    });
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <button
          onClick={lancer}
          disabled={loading}
          className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {loading ? "Recherche en cours…" : "Lancer la veille maintenant"}
        </button>
        {msg && (
          <span
            role="alert"
            aria-live="polite"
            className={`text-sm ${msg.startsWith("❌") ? "text-red-600" : "text-[var(--muted)]"}`}
          >
            {msg}
          </span>
        )}
      </div>

      {signaux.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-white p-8 text-center text-[var(--muted)]">
          Aucun signal pour l&apos;instant. Lance la veille — elle tourne aussi
          automatiquement chaque jour.
        </div>
      ) : (
        <div className="space-y-3">
          {signaux.map((s) => (
            <div
              key={s.id}
              className="rounded-xl border border-[var(--border)] bg-white p-4"
            >
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <span className="font-semibold">{s.entreprise}</span>
                {s.ville && (
                  <span className="text-sm text-[var(--muted)]">· {s.ville}</span>
                )}
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs">
                  {TYPE_LABEL[s.type ?? "autre"] ?? s.type}
                </span>
                <span className="ml-auto flex gap-1 text-xs">
                  <span className="rounded bg-emerald-100 px-1.5 py-0.5 font-semibold text-emerald-800">
                    intention {s.score_intention ?? "—"}
                  </span>
                  <span className="rounded bg-amber-100 px-1.5 py-0.5 font-semibold text-amber-800">
                    fit {s.score_fit ?? "—"}
                  </span>
                </span>
              </div>

              {s.declencheur && (
                <p className="text-sm">
                  <span className="font-medium">Déclencheur :</span> {s.declencheur}
                </p>
              )}
              {s.resume && (
                <p className="mt-1 text-sm text-[var(--muted)]">{s.resume}</p>
              )}
              {s.angle && (
                <p className="mt-1 rounded-lg bg-blue-50/50 px-3 py-2 text-sm">
                  💡 <span className="font-medium">Angle :</span> {s.angle}
                </p>
              )}

              <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
                {s.source_url && (
                  <a
                    href={s.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[var(--brand)] underline"
                  >
                    Source{s.source_date ? ` (${s.source_date})` : ""}
                  </a>
                )}
                {s.statut === "converti" ? (
                  <span className="rounded-full bg-emerald-100 px-2 py-0.5 font-medium text-emerald-800">
                    ✓ Converti en lead
                  </span>
                ) : (
                  <div className="ml-auto flex gap-2">
                    <button
                      disabled={pending}
                      onClick={() => act(() => retenirSignal(s.id))}
                      className="rounded-md bg-[var(--brand)] px-3 py-1 font-medium text-white disabled:opacity-50"
                    >
                      En faire un lead
                    </button>
                    <button
                      disabled={pending}
                      onClick={() => act(() => ecarterSignal(s.id))}
                      className="rounded-md border border-[var(--border)] px-3 py-1 font-medium hover:bg-slate-50 disabled:opacity-50"
                    >
                      Écarter
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
