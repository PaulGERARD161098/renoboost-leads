"use client";

import { useEffect, useRef, useState } from "react";
import { scoreColor } from "@/lib/ui";

type PotentielSolaire = {
  score: number;
  niveau: string;
  surface_toiture_m2?: number | null;
  surface_exploitable_m2?: number | null;
  type_toiture?: string | null;
  justification?: string;
};
type PotentielOmbrieres = {
  score: number;
  niveau: string;
  surface_parking_m2?: number | null;
  nb_places?: number | null;
  partage?: boolean | null;
  exploitant_probable?: string | null;
  justification?: string;
};
type PotentielBornes = {
  score: number;
  niveau: string;
  sur_site?: number;
  voisinage_1km?: number;
  rayon_10km?: number;
  types?: string[];
  justification?: string;
};

type Vision = {
  // v2 — 3 potentiels notés /10
  version?: number;
  solaire?: PotentielSolaire;
  ombrieres?: PotentielOmbrieres;
  bornes?: PotentielBornes;
  meilleur?: string;
  synthese?: string;
  // v1 (rétro-compatibilité)
  score?: number;
  verdict?: string;
  toiture?: { presente?: boolean; type?: string; surface_estimee_m2?: number | null };
  parking?: { present?: boolean; surface_estimee_m2?: number | null; ombrieres_possibles?: boolean };
  commentaire?: string;
  image_url?: string;
  analyse_le?: string;
  analyzed_at?: string;
};

type Echec = { message: string; action: string; retry: boolean };

/** Couleur d'une jauge /10. */
function gaugeColor(score: number): string {
  if (score >= 7) return "bg-emerald-100 text-emerald-800";
  if (score >= 4) return "bg-amber-100 text-amber-800";
  if (score >= 1) return "bg-orange-100 text-orange-800";
  return "bg-slate-100 text-slate-500";
}

function Gauge({ score }: { score: number }) {
  return (
    <div className="flex items-baseline gap-1">
      <span className={`rounded-md px-2 py-0.5 text-base font-bold ${gaugeColor(score)}`}>
        {score}
      </span>
      <span className="text-xs text-[var(--muted)]">/10</span>
    </div>
  );
}

function PotentielCard({
  icon,
  titre,
  score,
  niveau,
  lignes,
  justification,
  highlight,
}: {
  icon: string;
  titre: string;
  score: number;
  niveau: string;
  lignes: string[];
  justification?: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-lg border p-3 ${
        highlight ? "border-emerald-300 bg-emerald-50/40" : "border-[var(--border)] bg-white"
      }`}
    >
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-sm font-semibold">
          {icon} {titre}
        </span>
        <Gauge score={score} />
      </div>
      <p className="mb-1 text-xs font-medium text-[var(--muted)]">{niveau}</p>
      <ul className="space-y-0.5 text-xs text-[var(--muted)]">
        {lignes.map((l, i) => (
          <li key={i}>{l}</li>
        ))}
      </ul>
      {justification && <p className="mt-1.5 text-xs leading-relaxed">{justification}</p>}
    </div>
  );
}

export function SatellitePanel({
  leadId,
  initial,
  canAnalyse,
}: {
  leadId: string;
  initial: Record<string, unknown> | null;
  canAnalyse: boolean;
}) {
  const [result, setResult] = useState<Vision | null>((initial as Vision) ?? null);
  const [loading, setLoading] = useState(false);
  const [echec, setEchec] = useState<Echec | null>(null);
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

  const isV2 = result?.version === 2 && result.solaire && result.ombrieres && result.bornes;

  return (
    <div className="rounded-xl border border-[var(--border)] bg-white p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
          Potentiel du site (vue satellite IGN)
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
        <p className="text-sm text-[var(--muted)]">Analyse de la vue aérienne en cours…</p>
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

      {result && isV2 && (
        <div className="space-y-3">
          {result.synthese && (
            <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm font-medium">
              {result.synthese}
            </p>
          )}
          <div className="grid gap-3 lg:grid-cols-[200px_1fr]">
            {result.image_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={result.image_url}
                alt="Vue aérienne IGN centrée sur l'adresse"
                className="h-44 w-full rounded-lg object-cover lg:w-[200px]"
              />
            )}
            <div className="grid gap-3 sm:grid-cols-3">
              <PotentielCard
                icon="🔆"
                titre="Solaire"
                score={result.solaire!.score}
                niveau={result.solaire!.niveau}
                highlight={result.meilleur === "solaire"}
                lignes={[
                  result.solaire!.surface_exploitable_m2
                    ? `~${Math.round(result.solaire!.surface_exploitable_m2)} m² exploitables`
                    : "surface n.c.",
                  result.solaire!.type_toiture
                    ? `toiture ${result.solaire!.type_toiture}`
                    : "type n.c.",
                ]}
                justification={result.solaire!.justification}
              />
              <PotentielCard
                icon="🅿️"
                titre="Ombrières"
                score={result.ombrieres!.score}
                niveau={result.ombrieres!.niveau}
                highlight={result.meilleur === "ombrieres"}
                lignes={[
                  result.ombrieres!.nb_places
                    ? `~${result.ombrieres!.nb_places} places`
                    : "places n.c.",
                  result.ombrieres!.partage == null
                    ? "usage n.c."
                    : result.ombrieres!.partage
                      ? "parking partagé"
                      : "parking dédié",
                ]}
                justification={result.ombrieres!.justification}
              />
              <PotentielCard
                icon="🔌"
                titre="Bornes VE"
                score={result.bornes!.score}
                niveau={result.bornes!.niveau}
                highlight={result.meilleur === "bornes"}
                lignes={[
                  `${result.bornes!.sur_site ?? 0} sur site · ${result.bornes!.voisinage_1km ?? 0} à <1 km`,
                  `${result.bornes!.rayon_10km ?? 0} dans 10 km`,
                ]}
                justification={result.bornes!.justification}
              />
            </div>
          </div>
        </div>
      )}

      {result && !isV2 && (
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
            {result.commentaire && <p className="leading-relaxed">{result.commentaire}</p>}
          </div>
        </div>
      )}
    </div>
  );
}
