"use client";

import { useState } from "react";
import type { Lead, Run } from "@/lib/database.types";
import { RunCard, type RunCounts } from "./run-card";
import { LeadsTable } from "./leads-table";

/**
 * Recherche dépliable : la cartouche (RunCard) sert d'en-tête cliquable ;
 * au clic, la liste des prospects de la recherche se déroule (LeadsTable).
 */
export function RunGroup({
  run,
  cibleNom,
  counts,
  leads,
}: {
  run: Run;
  cibleNom: string;
  counts: RunCounts;
  leads: Lead[];
}) {
  const [open, setOpen] = useState(false);
  const toggle = () => setOpen((o) => !o);

  return (
    <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-white">
      <div
        role="button"
        tabIndex={0}
        onClick={toggle}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggle();
          }
        }}
        className="cursor-pointer hover:bg-slate-50"
      >
        <RunCard
          run={run}
          cibleNom={cibleNom}
          counts={counts}
          variant="header"
          chevron={open ? "open" : "closed"}
          detailHref={`/recherche/${run.id}`}
        />
      </div>
      {open && (
        <div className="border-t border-[var(--border)] p-4">
          {leads.length > 0 ? (
            <LeadsTable leads={leads} />
          ) : (
            <p className="text-sm text-[var(--muted)]">
              Aucun prospect pour cette recherche.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
