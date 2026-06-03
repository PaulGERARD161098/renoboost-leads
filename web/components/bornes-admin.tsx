"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

// Déclencheur d'ingestion des bornes, authentifié par la session CRM (aucun
// secret à manipuler). Affiche le résultat renvoyé par la route.
export function BornesAdmin() {
  const router = useRouter();
  const [loading, setLoading] = useState<null | string>(null);
  const [res, setRes] = useState<string | null>(null);

  async function lancer(source: "rossini" | "irve" | "all") {
    setLoading(source);
    setRes(null);
    try {
      const r = await fetch(`/api/bornes/ingest?source=${source}`, { method: "POST" });
      const data = await r.json();
      setRes(JSON.stringify(data, null, 2));
      router.refresh();
    } catch {
      setRes("Échec de l'appel (réessaie).");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="rounded-xl border border-[var(--border)] bg-white p-5">
      <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
        Charger / rafraîchir les bornes
      </h2>
      <p className="mb-3 text-sm text-[var(--muted)]">
        Importe les bornes Rossini Energy et l’open-data IRVE. Mise à jour aussi
        automatique chaque semaine.
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => lancer("rossini")}
          disabled={loading !== null}
          className="rounded-lg bg-[var(--brand)] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
        >
          {loading === "rossini" ? "Import Rossini…" : "Importer Rossini"}
        </button>
        <button
          onClick={() => lancer("irve")}
          disabled={loading !== null}
          className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm font-medium hover:bg-slate-50 disabled:opacity-40"
        >
          {loading === "irve" ? "Import IRVE… (long)" : "Importer IRVE (national)"}
        </button>
        <button
          onClick={() => lancer("all")}
          disabled={loading !== null}
          className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm font-medium hover:bg-slate-50 disabled:opacity-40"
        >
          {loading === "all" ? "Import…" : "Tout importer"}
        </button>
      </div>
      {res && (
        <pre className="mt-3 max-h-60 overflow-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
          {res}
        </pre>
      )}
    </div>
  );
}
