"use client";

import dynamic from "next/dynamic";
import type { RunMapProps } from "./run-map";
import { scoreToColor } from "./run-map";

// Leaflet a besoin du DOM : chargement client uniquement (pas de SSR).
const RunMap = dynamic(() => import("./run-map"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[420px] w-full items-center justify-center bg-slate-50 text-sm text-[var(--muted)]">
      Chargement de la carte…
    </div>
  ),
});

const LEGEND: { label: string; min: number }[] = [
  { label: "≥ 85", min: 85 },
  { label: "70–84", min: 70 },
  { label: "55–69", min: 55 },
  { label: "40–54", min: 40 },
  { label: "< 40", min: 0 },
];

export function RunMapLoader(props: RunMapProps) {
  return (
    <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-white">
      <RunMap {...props} />
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-[var(--border)] px-4 py-2 text-xs text-[var(--muted)]">
        <span className="font-medium">Qualification :</span>
        {LEGEND.map((l) => (
          <span key={l.label} className="inline-flex items-center gap-1">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: scoreToColor(l.min) }}
            />
            {l.label}
          </span>
        ))}
        <span className="inline-flex items-center gap-1">
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: scoreToColor(null) }}
          />
          non scoré
        </span>
        <span className="ml-auto">froid → chaud</span>
      </div>
    </div>
  );
}
