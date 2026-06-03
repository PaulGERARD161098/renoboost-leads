"use client";

import Link from "next/link";
import type { Run } from "@/lib/database.types";
import { RUN_STATUS_COLOR, RUN_STATUS_LABEL, formatDate, zoneLabel } from "@/lib/ui";

export type RunCounts = {
  total: number;
  top: number;
  horsFiltre: number;
};

/**
 * Cartouche d'une recherche (run) : cible, zone, statut + progression, compteurs.
 * Présentationnel — aucune logique interactive, pour pouvoir l'envelopper soit
 * dans un Link (liste des recherches) soit dans un toggle (groupe dépliable).
 *
 * - variant "card"   : carte autoportante (bordure + fond), pour une liste.
 * - variant "header" : sans bordure, pour servir d'en-tête d'un conteneur.
 */
export function RunCard({
  run,
  cibleNom,
  counts,
  variant = "card",
  chevron,
  detailHref,
}: {
  run: Run;
  cibleNom: string;
  counts: RunCounts;
  variant?: "card" | "header";
  chevron?: "open" | "closed";
  detailHref?: string;
}) {
  const enCours = run.status === "en_cours" || run.status === "demande";
  const wrap =
    variant === "card"
      ? "rounded-xl border border-[var(--border)] bg-white p-4"
      : "p-4";

  return (
    <div className={wrap}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            {chevron && (
              <span className="text-xs text-[var(--muted)]">
                {chevron === "open" ? "▾" : "▸"}
              </span>
            )}
            <span className="truncate font-semibold">{cibleNom}</span>
            <span className="shrink-0 text-sm text-[var(--muted)]">
              · {zoneLabel(run.zone)}
            </span>
          </div>
          <div className="mt-0.5 text-xs text-[var(--muted)]">
            {formatDate(run.created_at)}
          </div>
        </div>
        <span
          className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${RUN_STATUS_COLOR[run.status]}`}
        >
          {RUN_STATUS_LABEL[run.status]}
          {run.status === "en_cours" ? ` · ${run.progress}%` : ""}
        </span>
      </div>

      {enCours && (
        <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full bg-[var(--brand)] transition-all"
            style={{ width: `${Math.max(4, Math.min(100, run.progress))}%` }}
          />
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        <Metric value={counts.total} label="prospects" />
        {counts.top > 0 && (
          <Metric value={counts.top} label="top (≥ 75)" tone="text-emerald-700" />
        )}
        {counts.horsFiltre > 0 && (
          <Metric
            value={counts.horsFiltre}
            label="hors-filtre"
            tone="text-[var(--muted)]"
          />
        )}
        {detailHref && (
          <Link
            href={detailHref}
            onClick={(e) => e.stopPropagation()}
            className="ml-auto text-[var(--brand)] hover:underline"
          >
            Détail →
          </Link>
        )}
      </div>
    </div>
  );
}

function Metric({
  value,
  label,
  tone = "text-[var(--text)]",
}: {
  value: number;
  label: string;
  tone?: string;
}) {
  return (
    <span className="inline-flex items-baseline gap-1">
      <span className={`font-semibold ${tone}`}>{value}</span>
      <span className="text-[var(--muted)]">{label}</span>
    </span>
  );
}
