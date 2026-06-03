"use client";

import { useEffect, useRef, useState } from "react";
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

type Echec = { message: string; action: string; retry: boolean };

export function SatellitePanel({
  leadId,
  initial,
  canAnalyse,
}: {
  leadId: string;
  initial: Record<string, unknown> | null;
  // Faux quand le lead n'a ni coordonnées, ni adresse, ni ville : inutile de
  // tenter l'analyse, on affiche directement la cause.
  canAnalyse: boolean;
}) {
  const [result, setResult] = useState<Vision | null>((initial as Vision) ?? null);
  const [loading, setLoading] = useState(false);
  const [echec, setEchec] = useState<Echec | null>(null);
  // Empêche le double-déclenchement automatique (StrictMode monte deux fois).
  const autoLance = useRef(false);

  async function analyser() {
    setLoading(true);
    setEchec(null);
    try {
      const res = await fetch("/api/lead/satellite", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ leadId }),
      });
      const data = await res.json();
      if (data.error)
        setEchec({
          message: data.error,
          action: data.action ?? "Réessayer.",
          retry: data.retry ?? true,
        });
      else setResult(data.result as Vision);
    } catch {
      setEchec({
        message: "Connexion au serveur impossible.",
        action: "Vérifier la connexion, puis réessayer.",
        retry: true,
      });
    } finally {
      setLoading(false);
    }
  }

  // Auto-analyse à l'ouverture : si aucune analyse en cache, on la lance
  // (ou on affiche pourquoi elle ne peut pas tourner).
  useEffect(() => {
    if (autoLance.current || result) return;
    autoLance.current = true;
    if (canAnalyse) {
      analyser();
    } else {
      setEchec({
        message: "Pas de localisation : ni coordonnées, ni adresse, ni ville.",
        action: "Renseigner l'adresse ou la ville du lead, puis réessayer.",
        retry: false,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

      {loading && !result && (
        <p className="text-sm text-[var(--muted)]">
          Analyse de la vue aérienne en cours…
        </p>
      )}

      {!loading && echec && !result && (
        <div className="rounded-lg bg-amber-50 p-3 text-sm">
          <p className="font-medium text-amber-900">Analyse non disponible</p>
          <p className="mt-1 text-amber-800">{echec.message}</p>
          <p className="mt-1 text-amber-700">→ {echec.action}</p>
          {echec.retry && (
            <button
              onClick={analyser}
              className="mt-2 rounded-md border border-amber-300 bg-white px-2.5 py-1 text-xs font-medium text-amber-900 hover:bg-amber-100"
            >
              Réessayer
            </button>
          )}
        </div>
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
