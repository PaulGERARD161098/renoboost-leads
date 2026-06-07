"use client";

import { useState } from "react";
import { formatEur, normaliserCoutDetail, sommeCoutDetail } from "@/lib/costs";

/**
 * Décompte du coût réel par API (Google Places · Pappers · Dropcontact · Claude).
 * Progressive disclosure (charte) : un total cliquable qui déplie la ventilation.
 * Alimenté par `runs.cout_detail` (worker). Sans ventilation exploitable, on
 * retombe proprement sur le seul total.
 *
 * Réutilisé sur les 3 surfaces : rapport de fin, page détail d'une recherche,
 * tableau de bord (cumul tous runs).
 */
export function CoutDetailBadge({
  detail,
  total,
  defaultOpen = false,
  totalLabel = "Total",
}: {
  detail: Record<string, number> | null | undefined;
  /** Total à afficher (sinon somme des postes connus). Utile si `cout_eur` ≠ Σ. */
  total?: number;
  defaultOpen?: boolean;
  totalLabel?: string;
}) {
  const lignes = normaliserCoutDetail(detail);
  const somme = total != null ? total : sommeCoutDetail(detail);
  const [open, setOpen] = useState(defaultOpen);

  if (lignes.length === 0) {
    // Pas de ventilation (run ancien, démo sans coût, ou run échoué) : total nu.
    return <span className="font-bold">{formatEur(somme)}</span>;
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="group inline-flex items-center gap-1.5 text-left"
        aria-expanded={open}
      >
        <span className="font-bold">{formatEur(somme)}</span>
        <span className="text-xs text-[var(--muted)] group-hover:text-[var(--brand)]">
          {open ? "▾" : "▸"} détail
        </span>
      </button>
      {open && (
        <dl className="mt-2 space-y-1 border-t border-[var(--border)] pt-2">
          {lignes.map((l) => (
            <div key={l.cle} className="flex items-center justify-between gap-3 text-sm">
              <dt className="flex items-center gap-1.5 text-[var(--muted)]">
                <span className={`h-2 w-2 shrink-0 rounded-full ${l.couleur}`} />
                {l.label}
              </dt>
              <dd className="font-medium tabular-nums">{formatEur(l.montant)}</dd>
            </div>
          ))}
          <div className="flex items-center justify-between gap-3 border-t border-[var(--border)] pt-1 text-sm">
            <dt className="font-semibold">{totalLabel}</dt>
            <dd className="font-bold tabular-nums">{formatEur(somme)}</dd>
          </div>
        </dl>
      )}
    </div>
  );
}
