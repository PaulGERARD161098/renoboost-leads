"use client";

import dynamic from "next/dynamic";
import { densiteColor, DENSITE_PALIERS, type BornesMapProps } from "./bornes-map";

// Leaflet a besoin du DOM : chargement client uniquement.
const BornesMap = dynamic(() => import("./bornes-map"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[460px] w-full items-center justify-center bg-slate-50 text-sm text-[var(--muted)]">
      Chargement de la carte…
    </div>
  ),
});

export function BornesMapLoader({ counts }: BornesMapProps) {
  return (
    <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-white">
      <BornesMap counts={counts} />
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-[var(--border)] px-4 py-2 text-xs text-[var(--muted)]">
        <span className="font-medium">Bornes / département :</span>
        {DENSITE_PALIERS.map((p) => (
          <span key={p.label} className="inline-flex items-center gap-1">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: densiteColor(p.min) }}
            />
            {p.label}
          </span>
        ))}
      </div>
    </div>
  );
}
