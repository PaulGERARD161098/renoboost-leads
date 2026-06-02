"use client";

import { useState } from "react";
import { scoreColor } from "@/lib/ui";

type Vision = {
  score?: number;
  verdict?: string;
  toiture?: { presente?: boolean; type?: string; surface_estimee_m2?: number | null };
  parking?: {
    present?: boolean;
    surface_estimee_m2?: number | null;
    ombrieres_possibles?: boolean;
  };
  commentaire?: string;
  image_url?: string;
  analyse_le?: string;
};

export function SatellitePanel({
  leadId,
  initial,
}: {
  leadId: string;
  initial: Record<string, unknown> | null;
}) {
  const [result, setResult] = useState<Vision | null>((initial as Vision) ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function analyser() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/lead/satellite", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ leadId }),
      });
      const data = await res.json();
      if (data.error) setError(data.error);
      else setResult(data.result as Vision);
    } catch {
      setError("Connexion impossible. Réessaie.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-[var(--border)] bg-white p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
          Potentiel solaire (vue satellite IGN)
        </h2>
        <button
          onClick={analyser}
          disabled={loading}
          className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium hover:bg-slate-50 disabled:opacity-40"
        >
          {loading ? "Analyse…" : result ? "Réanalyser" : "Analyser"}
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {!result && !error && (
        <p className="text-sm text-[var(--muted)]">
          Lance une analyse de la vue aérienne pour estimer le potentiel toiture &
          ombrières de parking.
        </p>
      )}

      {result && (
        <div className="grid gap-4 md:grid-cols-[200px_1fr]">
          {result.image_url && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={result.image_url}
              alt="Vue aérienne IGN"
              className="h-40 w-full rounded-lg object-cover md:w-[200px]"
            />
          )}
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2">
              <span
                className={`rounded-md px-2 py-0.5 text-sm font-bold ${scoreColor(
                  typeof result.score === "number" ? result.score : null,
                )}`}
              >
                {typeof result.score === "number" ? result.score : "—"}/100
              </span>
              {result.verdict && <span className="font-medium">{result.verdict}</span>}
            </div>
            <ul className="space-y-1 text-[var(--muted)]">
              <li>
                🏠 Toiture :{" "}
                {result.toiture?.presente
                  ? `oui (${result.toiture.type ?? "type n.c."}${
                      result.toiture.surface_estimee_m2
                        ? `, ~${result.toiture.surface_estimee_m2} m²`
                        : ""
                    })`
                  : "non détectée"}
              </li>
              <li>
                🅿️ Parking :{" "}
                {result.parking?.present
                  ? `oui${
                      result.parking.surface_estimee_m2
                        ? ` (~${result.parking.surface_estimee_m2} m²)`
                        : ""
                    }${result.parking.ombrieres_possibles ? " · ombrières possibles" : ""}`
                  : "non détecté"}
              </li>
            </ul>
            {result.commentaire && (
              <p className="leading-relaxed">{result.commentaire}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
