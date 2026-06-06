"use client";

import Link from "next/link";
import type { Run } from "@/lib/database.types";
import { RUN_STATUS_COLOR, RUN_STATUS_LABEL, formatDate, zoneLabel } from "@/lib/ui";

export type RunCounts = {
  total: number;
  top: number;
  horsFiltre: number;
};

const QUALITE_BADGE: Record<string, { label: string; tone: string }> = {
  bonne: { label: "Bonne moisson", tone: "bg-emerald-100 text-emerald-800" },
  moyenne: { label: "Moisson moyenne", tone: "bg-amber-100 text-amber-800" },
  mauvaise: { label: "Faible moisson", tone: "bg-slate-200 text-slate-600" },
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
  actions,
}: {
  run: Run;
  cibleNom: string;
  counts: RunCounts;
  variant?: "card" | "header";
  chevron?: "open" | "closed";
  detailHref?: string;
  actions?: React.ReactNode;
}) {
  const enCours = run.status === "en_cours" || run.status === "demande";
  const qualite = run.qualite ? QUALITE_BADGE[run.qualite] : null;
  const wrap =
    variant === "card"
      ? "rounded-xl border border-[var(--border)] bg-white p-4"
      : "p-4";

  return (
    <div className={wrap}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            {chevron && (
              <span className="text-xs text-[var(--muted)]">
                {chevron === "open" ? "▾" : "▸"}
              </span>
            )}
            <span className="truncate font-semibold">
              {run.nom || cibleNom}
            </span>
            <span className="shrink-0 text-sm text-[var(--muted)]">
              · {zoneLabel(run.zone)}
            </span>
            {run.is_test && (
              <span className="shrink-0 rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-violet-700">
                Test
              </span>
            )}
            {run.archive && (
              <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-500">
                Archivée
              </span>
            )}
            {qualite && (
              <span
                className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${qualite.tone}`}
              >
                {qualite.label}
              </span>
            )}
          </div>
          <div className="mt-0.5 text-xs text-[var(--muted)]">
            {run.nom ? `${cibleNom} · ` : ""}
            {formatDate(run.created_at)}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${RUN_STATUS_COLOR[run.status]}`}
          >
            {RUN_STATUS_LABEL[run.status]}
            {run.status === "en_cours" ? ` · ${run.progress}%` : ""}
          </span>
          {actions}
        </div>
      </div>

      {enCours && (
        <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full bg-[var(--brand)] transition-all"
            style={{ width: `${Math.max(4, Math.min(100, run.progress))}%` }}
          />
        </div>
      )}

      {run.status === "echoue" && run.erreur && (
        <p className="mt-2 rounded-lg bg-red-50 px-3 py-1.5 text-xs text-red-700">
          ⚠ {run.erreur}
        </p>
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
