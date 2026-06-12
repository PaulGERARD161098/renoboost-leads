"use client";

import dynamic from "next/dynamic";
import { CATEGORIE_META, type CategorieTournee, type PointTournee } from "@/lib/tournees";

// Leaflet a besoin du DOM : chargement client uniquement.
const TourneeMap = dynamic(() => import("./tournee-map"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[520px] w-full items-center justify-center bg-slate-50 text-sm text-[var(--muted)]">
      Chargement de la carte…
    </div>
  ),
});

export function TourneeMapLoader({ points }: { points: PointTournee[] }) {
  const cats: CategorieTournee[] = ["rdv", "chaud", "tiede"];
  return (
    <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-white">
      <TourneeMap points={points} />
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-[var(--border)] px-4 py-2 text-xs text-[var(--muted)]">
        {cats.map((c) => (
          <span key={c} className="inline-flex items-center gap-1">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: CATEGORIE_META[c].color }}
            />
            {CATEGORIE_META[c].emoji} {CATEGORIE_META[c].label}
          </span>
        ))}
      </div>
    </div>
  );
}
