"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

// Bouton d'import IRVE, authentifié par la session CRM (aucun secret).
export function BornesAdmin() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [res, setRes] = useState<string | null>(null);

  async function importer() {
    setLoading(true);
    setRes(null);
    try {
      const r = await fetch("/api/bornes/ingest", { method: "POST" });
      const data = await r.json();
      setRes(JSON.stringify(data, null, 2));
      router.refresh();
    } catch {
      setRes("Échec de l'appel (réessaie).");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-[var(--border)] bg-white p-5">
      <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
        Données IRVE
      </h2>
      <p className="mb-3 text-sm text-[var(--muted)]">
        Importe le fichier consolidé national des bornes (open-data data.gouv).
        Rafraîchi aussi automatiquement chaque semaine. L’import complet prend ~1 min.
      </p>
      <button
        onClick={importer}
        disabled={loading}
        className="rounded-lg bg-[var(--brand)] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40"
      >
        {loading ? "Import en cours… (~1 min)" : "Importer / rafraîchir IRVE"}
      </button>
      {res && (
        <pre className="mt-3 max-h-60 overflow-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
          {res}
        </pre>
      )}
    </div>
  );
}
