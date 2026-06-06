"use client";

import { useEffect, useState } from "react";
import type { RunReport } from "@/lib/run-report";
import { formatDuree } from "@/lib/run-report";
import { RUN_STATUS_COLOR, RUN_STATUS_LABEL, formatDate } from "@/lib/ui";

/**
 * Rapport de fin de recherche — coûts, temps, périmètre précis, entreprises
 * ciblées. Deux usages :
 *  - mode "button" : bouton « 📄 Rapport » réouvrable (fiche recherche) ;
 *  - mode "auto"   : s'ouvre tout seul une fois quand un run vient de finir
 *    (page Recherche), mémorisé en localStorage pour ne pas se rejouer.
 */
export function RunReportLauncher({
  report,
  mode = "button",
}: {
  report: RunReport;
  mode?: "button" | "auto";
}) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (mode !== "auto") return;
    if (report.statut !== "termine" && report.statut !== "echoue") return;
    const key = `run-report-seen:${report.runId}:${report.finishedAt ?? ""}`;
    try {
      if (localStorage.getItem(key)) return;
      localStorage.setItem(key, "1");
      setOpen(true);
    } catch {
      /* localStorage indisponible : on n'auto-ouvre pas */
    }
  }, [mode, report.runId, report.finishedAt, report.statut]);

  return (
    <>
      {mode === "button" && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="rounded-lg border border-[var(--border)] bg-white px-3 py-1.5 text-sm font-medium hover:border-[var(--brand)] hover:text-[var(--brand)]"
        >
          📄 Rapport de fin de recherche
        </button>
      )}
      {open && <RunReportModal report={report} onClose={() => setOpen(false)} />}
    </>
  );
}

function RunReportModal({ report, onClose }: { report: RunReport; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const p = report.perimetre;
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 backdrop-blur-sm sm:items-center"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="my-auto w-full max-w-2xl rounded-2xl border border-[var(--border)] bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* En-tête */}
        <div className="flex items-start justify-between gap-3 rounded-t-2xl bg-gradient-to-br from-[var(--brand)]/10 to-transparent px-6 pb-4 pt-5">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-bold">📄 {report.titre}</h2>
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${RUN_STATUS_COLOR[report.statut]}`}
              >
                {RUN_STATUS_LABEL[report.statut]}
              </span>
            </div>
            <p className="mt-0.5 text-xs text-[var(--muted)]">
              {report.cibleNom} · lancée le {formatDate(report.createdAt)}
              {report.finishedAt ? ` · finie le ${formatDate(report.finishedAt)}` : ""}
            </p>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 rounded-lg px-2 py-1 text-sm text-[var(--muted)] hover:bg-slate-100"
          >
            ✕
          </button>
        </div>

        <div className="space-y-5 px-6 pb-6 pt-1">
          {/* Chiffres clés */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Kpi label="Durée" value={formatDuree(report.dureeS)} />
            <Kpi label="Coût total" value={`${report.coutTotal.toFixed(2)} €`} />
            <Kpi
              label="Coût / qualifié"
              value={report.coutParQualifie != null ? `${report.coutParQualifie.toFixed(2)} €` : "—"}
            />
            <Kpi label="Score moyen" value={report.scoreMoyen != null ? String(report.scoreMoyen) : "—"} />
          </div>

          {/* Périmètre */}
          <Section titre="🎯 Périmètre ciblé">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
              <Row k="Cible" v={p.cible} />
              <Row k="Zone" v={p.zone} />
              <Row k="Effectif min." v={p.effectifMin != null ? `${p.effectifMin}+` : "—"} />
              <Row k="Volume visé" v={p.volumeCible != null ? String(p.volumeCible) : "—"} />
              <Row k="Budget" v={p.budgetEur != null ? `${p.budgetEur} €` : "—"} />
            </dl>
          </Section>

          {/* Récolte */}
          <Section titre="📊 Récolte">
            <div className="mb-2 flex flex-wrap gap-x-5 gap-y-1 text-sm">
              <Metric n={report.counts.total} label="découverts" />
              <Metric n={report.counts.qualifies} label="qualifiés" tone="text-[var(--brand)]" />
              <Metric n={report.counts.top} label="top (≥ 75)" tone="text-emerald-700" />
              <Metric n={report.counts.horsFiltre} label="hors-filtre" tone="text-[var(--muted)]" />
            </div>
            {report.taux ? (
              <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-[var(--muted)]">
                <span>
                  ✉️ email <b className="text-[var(--text)]">{report.taux.email}%</b>
                </span>
                <span>
                  👤 dirigeant <b className="text-[var(--text)]">{report.taux.contactNom}%</b>
                </span>
                <span>
                  ☎️ téléphone <b className="text-[var(--text)]">{report.taux.tel}%</b>
                </span>
                <span className="text-xs">(sur les qualifiés)</span>
              </div>
            ) : (
              <p className="text-sm text-[var(--muted)]">Aucun lead qualifié sur ce run.</p>
            )}
          </Section>

          {/* Entreprises ciblées */}
          <Section titre={`🏢 Entreprises ciblées (${report.entreprises.length})`}>
            {report.entreprises.length === 0 ? (
              <p className="text-sm text-[var(--muted)]">Aucune entreprise.</p>
            ) : (
              <div className="max-h-64 overflow-y-auto rounded-lg border border-[var(--border)]">
                <table className="w-full text-sm">
                  <tbody>
                    {report.entreprises.map((e, i) => (
                      <tr key={i} className="border-b border-[var(--border)] last:border-0">
                        <td className="px-3 py-1.5">
                          <span className="font-medium">{e.entreprise}</span>
                          {e.ville && <span className="text-[var(--muted)]"> · {e.ville}</span>}
                          {e.horsFiltre && (
                            <span className="ml-1 rounded bg-slate-100 px-1 text-[10px] text-slate-500">
                              hors-filtre
                            </span>
                          )}
                        </td>
                        <td className="whitespace-nowrap px-3 py-1.5 text-right text-xs text-[var(--muted)]">
                          {e.email ? "✉️" : ""} {e.tel ? "☎️" : ""}{" "}
                          {e.score != null && (
                            <span className="font-semibold text-[var(--text)]">{e.score}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>
        </div>
      </div>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-slate-50 px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-[var(--muted)]">{label}</div>
      <div className="text-base font-bold">{value}</div>
    </div>
  );
}

function Section({ titre, children }: { titre: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
        {titre}
      </div>
      {children}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-[var(--muted)]">{k}</dt>
      <dd className="text-right font-medium">{v}</dd>
    </div>
  );
}

function Metric({ n, label, tone = "text-[var(--text)]" }: { n: number; label: string; tone?: string }) {
  return (
    <span className="inline-flex items-baseline gap-1">
      <span className={`font-semibold ${tone}`}>{n}</span>
      <span className="text-[var(--muted)]">{label}</span>
    </span>
  );
}
