"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import type { LeadStatus } from "@/lib/database.types";
import { LEAD_STATUS_COLOR, LEAD_STATUS_LABEL, scoreColor } from "@/lib/ui";
import { solaireFromVision } from "@/lib/outreach";
import { estimerSolaire, fmtEur, fmtKwc, fmtKwh } from "@/lib/solaire";

export type SolaireLead = {
  id: string;
  entreprise: string;
  ville: string | null;
  codePostal: string | null;
  statut: LeadStatus;
  scoreCommercial: number | null;
  scoreSolaire: number | null;
  latitude: number | null;
  longitude: number | null;
  analyse: boolean;
  canAnalyse: boolean;
  toitureM2: number | null;
  parkingM2: number | null;
  ombrieres: boolean | null;
  kwc: number | null;
  productionKwhAn: number | null;
  caAnnuelEur: number | null;
};

// Carte (Leaflet → DOM only) chargée côté client, sans SSR.
const SolaireMap = dynamic(() => import("./run-map"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[420px] items-center justify-center bg-slate-50 text-sm text-[var(--muted)]">
      Chargement de la carte…
    </div>
  ),
});

type Filtre = "tous" | "fort" | "moyen";
type Vue = "liste" | "carte";

type Draft =
  | { leadId: string; loading: true }
  | { leadId: string; loading: false; sujet?: string; corps?: string; error?: string };

export function SolaireWorkspace({ leads: initial }: { leads: SolaireLead[] }) {
  const [leads, setLeads] = useState<SolaireLead[]>(initial);
  const [filtre, setFiltre] = useState<Filtre>("tous");
  const [toitureOnly, setToitureOnly] = useState(false);
  const [ombrieresOnly, setOmbrieresOnly] = useState(false);
  const [q, setQ] = useState("");
  const [vue, setVue] = useState<Vue>("liste");
  const [batch, setBatch] = useState<{ running: boolean; done: number; total: number }>({
    running: false,
    done: 0,
    total: 0,
  });
  const [draft, setDraft] = useState<Draft | null>(null);

  // ── Contexte : agrégats sur les leads analysés ──────────────────────
  const analyses = leads.filter((l) => l.analyse);
  const fortPotentiel = analyses.filter((l) => (l.scoreSolaire ?? 0) >= 75).length;
  const kwcCumule = analyses.reduce((s, l) => s + (l.kwc ?? 0), 0);
  const caCumule = analyses.reduce((s, l) => s + (l.caAnnuelEur ?? 0), 0);
  // Cibles d'analyse par lot : localisables et pas encore analysés.
  const aAnalyser = leads.filter((l) => l.canAnalyse && !l.analyse);

  // ── Filtrage + tri (potentiel solaire décroissant) ──────────────────
  const visibles = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return leads
      .filter((l) => {
        if (filtre === "fort" && (l.scoreSolaire ?? -1) < 75) return false;
        if (filtre === "moyen" && (l.scoreSolaire ?? -1) < 50) return false;
        if (toitureOnly && !(l.toitureM2 && l.toitureM2 > 0)) return false;
        if (ombrieresOnly && !l.ombrieres) return false;
        if (needle) {
          const hay = `${l.entreprise} ${l.ville ?? ""} ${l.codePostal ?? ""}`.toLowerCase();
          if (!hay.includes(needle)) return false;
        }
        return true;
      })
      .sort((a, b) => {
        // Analysés d'abord (par score solaire), puis non analysés.
        const sa = a.scoreSolaire ?? (a.analyse ? 0 : -1);
        const sb = b.scoreSolaire ?? (b.analyse ? 0 : -1);
        return sb - sa;
      });
  }, [leads, filtre, toitureOnly, ombrieresOnly, q]);

  const geoloc = visibles.filter(
    (l) => typeof l.latitude === "number" && typeof l.longitude === "number",
  );

  // Applique le résultat d'une analyse satellite à un lead (en place).
  function applyVision(id: string, result: Record<string, unknown>) {
    const surfaces = solaireFromVision(result);
    const estim = surfaces ? estimerSolaire(surfaces) : null;
    const score =
      typeof (result as { score?: number }).score === "number"
        ? (result as { score: number }).score
        : null;
    setLeads((prev) =>
      prev.map((l) =>
        l.id === id
          ? {
              ...l,
              analyse: true,
              scoreSolaire: score ?? l.scoreSolaire,
              toitureM2: surfaces?.toiture_m2 ?? null,
              parkingM2: surfaces?.parking_m2 ?? null,
              ombrieres: surfaces?.ombrieres ?? null,
              kwc: estim?.kwc ?? null,
              productionKwhAn: estim?.productionKwhAn ?? null,
              caAnnuelEur: estim?.caAnnuelEur ?? null,
            }
          : l,
      ),
    );
  }

  async function analyserUn(id: string): Promise<void> {
    try {
      const res = await fetch("/api/lead/satellite", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ leadId: id }),
      });
      const data = await res.json();
      if (data.ok && data.result) applyVision(id, data.result);
    } catch {
      /* échec silencieux : on continue le lot, le lead reste « non analysé » */
    }
  }

  // Analyse par lot : séquentielle (concurrence 1) pour respecter le budget IA.
  async function analyserLot(cibles: SolaireLead[]) {
    if (!cibles.length || batch.running) return;
    setBatch({ running: true, done: 0, total: cibles.length });
    for (const c of cibles) {
      await analyserUn(c.id);
      setBatch((b) => ({ ...b, done: b.done + 1 }));
    }
    setBatch((b) => ({ ...b, running: false }));
  }

  async function genererApproche(lead: SolaireLead) {
    setDraft({ leadId: lead.id, loading: true });
    try {
      const res = await fetch("/api/lead/outreach-draft", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ leadId: lead.id, mode: "approche" }),
      });
      const data = await res.json();
      if (data.error) setDraft({ leadId: lead.id, loading: false, error: data.error });
      else setDraft({ leadId: lead.id, loading: false, sujet: data.sujet, corps: data.corps });
    } catch {
      setDraft({ leadId: lead.id, loading: false, error: "Connexion impossible." });
    }
  }

  return (
    <div>
      {/* ── Contexte : où on en est ── */}
      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Sites analysés" value={`${analyses.length} / ${leads.length}`} />
        <Stat label="Fort potentiel (≥75)" value={fortPotentiel} />
        <Stat label="Puissance cumulée" value={kwcCumule ? fmtKwc(kwcCumule) : "—"} />
        <Stat label="CA annuel estimé" value={caCumule ? fmtEur(caCumule) : "—"} />
      </div>

      {/* ── Actions recommandées ── */}
      <div className="mb-5 rounded-2xl border border-[var(--brand)]/30 bg-gradient-to-br from-[var(--brand)]/5 to-transparent p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm">
            <span className="font-semibold">⚡ Action recommandée — </span>
            {aAnalyser.length > 0 ? (
              <span>
                {aAnalyser.length} site{aAnalyser.length > 1 ? "s" : ""} localisé
                {aAnalyser.length > 1 ? "s" : ""} pas encore analysé
                {aAnalyser.length > 1 ? "s" : ""}. Lance l&apos;analyse en lot pour
                révéler leur potentiel solaire.
              </span>
            ) : (
              <span className="text-[var(--muted)]">
                Tous les sites localisables sont analysés. Filtre les forts
                potentiels et génère les approches.
              </span>
            )}
          </div>
          <button
            onClick={() => analyserLot(aAnalyser)}
            disabled={batch.running || aAnalyser.length === 0}
            className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--brand-dark)] disabled:opacity-40"
          >
            {batch.running
              ? `Analyse… ${batch.done}/${batch.total}`
              : `Analyser le lot (${aAnalyser.length})`}
          </button>
        </div>
        {batch.running && (
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-white">
            <div
              className="h-full bg-[var(--brand)] transition-all"
              style={{
                width: `${batch.total ? Math.round((batch.done / batch.total) * 100) : 0}%`,
              }}
            />
          </div>
        )}
      </div>

      {/* ── Barre filtres + bascule vue ── */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Rechercher une entreprise, ville…"
          className="w-56 rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm outline-none focus:border-[var(--brand)]"
        />
        <select
          value={filtre}
          onChange={(e) => setFiltre(e.target.value as Filtre)}
          className="rounded-lg border border-[var(--border)] px-2 py-1.5 text-sm"
        >
          <option value="tous">Tous les scores</option>
          <option value="moyen">Potentiel ≥ 50</option>
          <option value="fort">Fort potentiel ≥ 75</option>
        </select>
        <label className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-2.5 py-1.5 text-sm">
          <input
            type="checkbox"
            checked={toitureOnly}
            onChange={(e) => setToitureOnly(e.target.checked)}
          />
          🏠 Toiture
        </label>
        <label className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-2.5 py-1.5 text-sm">
          <input
            type="checkbox"
            checked={ombrieresOnly}
            onChange={(e) => setOmbrieresOnly(e.target.checked)}
          />
          🅿️ Ombrières
        </label>
        <div className="ml-auto flex overflow-hidden rounded-lg border border-[var(--border)]">
          {(["liste", "carte"] as Vue[]).map((v) => (
            <button
              key={v}
              onClick={() => setVue(v)}
              className={`px-3 py-1.5 text-sm font-medium capitalize ${
                vue === v ? "bg-[var(--brand)] text-white" : "bg-white text-[var(--muted)]"
              }`}
            >
              {v === "liste" ? "Liste" : "Carte"}
            </button>
          ))}
        </div>
      </div>

      {/* ── Données ── */}
      {vue === "carte" ? (
        <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-white">
          {geoloc.length ? (
            <SolaireMap
              leads={geoloc.map((l) => ({
                id: l.id,
                entreprise: l.entreprise,
                ville: l.ville,
                score: l.scoreSolaire,
                latitude: l.latitude,
                longitude: l.longitude,
              }))}
            />
          ) : (
            <p className="p-6 text-sm text-[var(--muted)]">
              Aucun site géolocalisé dans la sélection. Lance des analyses pour
              géocoder les leads.
            </p>
          )}
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs text-[var(--muted)]">
              <tr>
                <th className="px-4 py-2 font-medium">Entreprise</th>
                <th className="px-4 py-2 font-medium">☀️ Potentiel</th>
                <th className="px-4 py-2 font-medium">Puissance</th>
                <th className="px-4 py-2 font-medium">CA estimé</th>
                <th className="px-4 py-2 font-medium">Statut</th>
                <th className="px-4 py-2 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {visibles.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-[var(--muted)]">
                    Aucun site ne correspond à ces filtres.
                  </td>
                </tr>
              ) : (
                visibles.slice(0, 300).map((l) => (
                  <tr
                    key={l.id}
                    className="border-t border-[var(--border)] align-top hover:bg-slate-50"
                  >
                    <td className="px-4 py-2.5">
                      <Link
                        href={`/leads/${l.id}`}
                        className="font-medium hover:text-[var(--brand)]"
                      >
                        {l.entreprise}
                      </Link>
                      <div className="text-xs text-[var(--muted)]">
                        {l.ville ?? "—"}
                        {l.toitureM2 ? ` · toiture ~${l.toitureM2} m²` : ""}
                        {l.ombrieres ? " · ombrières" : ""}
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      {l.analyse ? (
                        <span
                          className={`rounded px-1.5 py-0.5 text-xs font-semibold ${scoreColor(l.scoreSolaire)}`}
                        >
                          {l.scoreSolaire ?? "—"}
                        </span>
                      ) : (
                        <span className="text-xs text-[var(--muted)]">non analysé</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      {l.kwc ? (
                        <span title={l.productionKwhAn ? fmtKwh(l.productionKwhAn) : undefined}>
                          {fmtKwc(l.kwc)}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      {l.caAnnuelEur ? fmtEur(l.caAnnuelEur) : "—"}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${LEAD_STATUS_COLOR[l.statut]}`}
                      >
                        {LEAD_STATUS_LABEL[l.statut]}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex justify-end gap-1.5">
                        <button
                          onClick={() => analyserUn(l.id)}
                          disabled={!l.canAnalyse || batch.running}
                          title={
                            l.canAnalyse
                              ? undefined
                              : "Lead sans localisation : renseigne l'adresse ou la ville."
                          }
                          className="rounded-md border border-[var(--border)] px-2 py-1 text-xs font-medium hover:bg-slate-100 disabled:opacity-40"
                        >
                          {l.analyse ? "Réanalyser" : "Analyser"}
                        </button>
                        {l.analyse && (
                          <button
                            onClick={() => genererApproche(l)}
                            className="rounded-md border border-[var(--brand)] bg-[var(--brand)]/5 px-2 py-1 text-xs font-medium text-[var(--brand)] hover:bg-[var(--brand)]/10"
                          >
                            ✉️ Approche
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Modale brouillon d'approche solaire ── */}
      {draft && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-sm"
          onClick={() => setDraft(null)}
        >
          <div
            className="w-full max-w-xl rounded-2xl border border-[var(--border)] bg-white shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-3">
              <h3 className="font-semibold">✉️ Approche solaire</h3>
              <button
                onClick={() => setDraft(null)}
                className="rounded-md px-2 py-1 text-[var(--muted)] hover:bg-slate-100"
              >
                ✕
              </button>
            </div>
            <div className="space-y-3 p-5">
              {draft.loading ? (
                <p className="text-sm text-[var(--muted)]">
                  ✨ Génération du brouillon (toiture/ombrières prises en compte)…
                </p>
              ) : draft.error ? (
                <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
                  {draft.error}
                </p>
              ) : (
                <>
                  {draft.sujet && (
                    <div>
                      <div className="text-xs font-medium uppercase text-[var(--muted)]">
                        Sujet
                      </div>
                      <p className="text-sm font-medium">{draft.sujet}</p>
                    </div>
                  )}
                  <div>
                    <div className="text-xs font-medium uppercase text-[var(--muted)]">
                      Message
                    </div>
                    <pre className="mt-1 max-h-72 overflow-y-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-sm leading-relaxed">
                      {draft.corps}
                    </pre>
                  </div>
                  <div className="flex items-center justify-between">
                    <button
                      onClick={() =>
                        navigator.clipboard?.writeText(
                          `${draft.sujet ? draft.sujet + "\n\n" : ""}${draft.corps ?? ""}`,
                        )
                      }
                      className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm font-medium hover:bg-slate-50"
                    >
                      Copier
                    </button>
                    <Link
                      href={`/leads/${draft.leadId}`}
                      className="text-sm font-medium text-[var(--brand)] hover:underline"
                    >
                      Ouvrir la fiche pour envoyer →
                    </Link>
                  </div>
                  <p className="text-xs text-[var(--muted)]">
                    Brouillon — rien n&apos;est envoyé. Validation et envoi se font
                    depuis la fiche du prospect.
                  </p>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-white p-3">
      <div className="text-lg font-bold">{value}</div>
      <div className="text-xs text-[var(--muted)]">{label}</div>
    </div>
  );
}
