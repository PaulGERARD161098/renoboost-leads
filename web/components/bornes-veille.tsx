"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { VeilleSignal } from "@/lib/database.types";
import { VeilleList } from "@/components/veille-list";

// Veille d'intentions VE intégrée à l'onglet Bornes : lance une veille web
// (signaux flotte VE / ombrières / électrification) scopable par département,
// puis affiche les signaux. Action distincte de l'import IRVE.
export function BornesVeille({
  signaux,
  initialDept = "",
}: {
  signaux: VeilleSignal[];
  // Département pré-rempli depuis le radar (« Veille VE ici »). L'utilisateur
  // garde la main : on pré-remplit, on ne lance pas (garde-fou anti-dépense).
  initialDept?: string;
}) {
  const router = useRouter();
  const [dept, setDept] = useState(initialDept);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function lancer() {
    setLoading(true);
    setMsg(null);
    try {
      const qs = dept.trim() ? `?dept=${encodeURIComponent(dept.trim())}` : "";
      const r = await fetch(`/api/veille/run${qs}`, { method: "POST" });
      const data = await r.json();
      setMsg(
        data.error
          ? data.error
          : `${data.inserted ?? 0} nouveau(x) signal(aux) (sur ${data.total ?? 0} trouvés).`,
      );
      router.refresh();
    } catch {
      setMsg("Échec de l'appel (réessaie).");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div
        id="veille-ve"
        className={`rounded-xl border bg-white p-5 ${
          initialDept ? "border-[var(--brand)] ring-1 ring-[var(--brand)]/30" : "border-[var(--border)]"
        }`}
      >
        <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
          🛰️ Veille d'intentions VE
        </h2>
        <p className="mb-3 text-sm text-[var(--muted)]">
          Cherche sur le web des signaux d'achat (flotte VE, ombrières, électrification).
          Laisse vide pour le périmètre cibles, ou cible un département.
          {initialDept && (
            <span className="ml-1 font-medium text-[var(--brand)]">
              Département {initialDept} pré-rempli depuis le radar — clique pour lancer.
            </span>
          )}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={dept}
            onChange={(e) => setDept(e.target.value)}
            placeholder="Département (ex. 59) — optionnel"
            className="w-56 rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm outline-none focus:border-[var(--brand)]"
          />
          <button
            onClick={lancer}
            disabled={loading}
            className="rounded-lg bg-[var(--brand)] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
          >
            {loading ? "Veille en cours… (~1 min)" : "Lancer la veille VE"}
          </button>
          {msg && <span className="text-xs text-[var(--muted)]">{msg}</span>}
        </div>
      </div>

      <VeilleList signaux={signaux} />
    </div>
  );
}
