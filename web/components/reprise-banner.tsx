"use client";

import { useState, useTransition } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { AppContext, Deadline } from "@/lib/database.types";
import { genererResumeSession, updateAppContext } from "@/lib/actions/context";
import { logSuggestionClick } from "@/lib/actions/tracking";

type Action = { label: string; href: string; n: number };

function joursRestants(date: string): number {
  const d = new Date(date + "T23:59:59");
  return Math.ceil((d.getTime() - Date.now()) / 86_400_000);
}

export function RepriseBanner({
  context,
  actions,
}: {
  context: AppContext;
  actions: Action[];
}) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [pending, start] = useTransition();
  const [regen, startRegen] = useTransition();

  function regenererResume() {
    startRegen(async () => {
      await genererResumeSession();
      router.refresh();
    });
  }

  const [objectif, setObjectif] = useState(context.objectif_final ?? "");
  const [client, setClient] = useState(context.client_actif ?? "");
  const [resume, setResume] = useState(context.resume_session ?? "");
  const [deadlines, setDeadlines] = useState<Deadline[]>(context.deadlines ?? []);

  const dlTriees = [...(context.deadlines ?? [])].sort((a, b) => a.date.localeCompare(b.date));
  const actionsUtiles = actions.filter((a) => a.n > 0);

  function save() {
    start(async () => {
      await updateAppContext({
        objectif_final: objectif,
        client_actif: client,
        resume_session: resume,
        deadlines,
      });
      setEditing(false);
      router.refresh();
    });
  }

  return (
    <div className="mb-6 rounded-2xl border border-[var(--brand)]/30 bg-gradient-to-br from-[var(--brand)]/5 to-transparent p-5">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-base font-bold">👋 Reprise</h2>
        <div className="flex items-center gap-2">
          <button
            onClick={regenererResume}
            disabled={regen}
            title="Générer automatiquement le récap depuis l'activité récente"
            className="rounded-lg border border-[var(--border)] bg-white px-2.5 py-1 text-xs font-medium hover:bg-slate-50 disabled:opacity-40"
          >
            {regen ? "Génération…" : "✨ Générer le récap"}
          </button>
          <button
            onClick={() => setEditing((v) => !v)}
            className="rounded-lg border border-[var(--border)] bg-white px-2.5 py-1 text-xs font-medium hover:bg-slate-50"
          >
            {editing ? "Fermer" : "Éditer"}
          </button>
        </div>
      </div>

      {!editing ? (
        <div className="grid gap-4 md:grid-cols-3">
          {/* Objectif + client */}
          <div className="space-y-2">
            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
                🎯 Objectif final
              </div>
              <p className="text-sm">
                {context.objectif_final || (
                  <span className="text-[var(--muted)]">À définir (bouton Éditer).</span>
                )}
              </p>
            </div>
            {context.client_actif && (
              <div className="text-sm">
                <span className="text-[var(--muted)]">👤 Client : </span>
                <span className="font-medium">{context.client_actif}</span>
              </div>
            )}
          </div>

          {/* Deadlines + récap */}
          <div className="space-y-2">
            <div className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
              ⏰ Deadlines
            </div>
            {dlTriees.length ? (
              <ul className="space-y-1 text-sm">
                {dlTriees.slice(0, 3).map((d) => {
                  const j = joursRestants(d.date);
                  return (
                    <li key={d.label + d.date} className="flex items-center justify-between gap-2">
                      <span className="truncate">{d.label}</span>
                      <span
                        className={`shrink-0 text-xs font-medium ${
                          j < 0 ? "text-red-600" : j <= 3 ? "text-amber-600" : "text-[var(--muted)]"
                        }`}
                      >
                        {j < 0 ? `J+${-j}` : j === 0 ? "aujourd'hui" : `J−${j}`}
                      </span>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="text-sm text-[var(--muted)]">Aucune deadline.</p>
            )}
            {context.resume_session && (
              <p className="mt-1 rounded-lg bg-white/70 px-3 py-2 text-sm leading-relaxed text-slate-700">
                📝 {context.resume_session}
              </p>
            )}
          </div>

          {/* Prochaines actions */}
          <div className="space-y-2">
            <div className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
              ⚡ Prochaines actions
            </div>
            {actionsUtiles.length ? (
              <div className="flex flex-col gap-1.5">
                {actionsUtiles.map((a) => (
                  <Link
                    key={a.label}
                    href={a.href}
                    onClick={() => void logSuggestionClick("reprise_banner", a.label, a.href)}
                    className="flex items-center justify-between rounded-lg border border-[var(--border)] bg-white px-3 py-1.5 text-sm hover:border-[var(--brand)]"
                  >
                    <span>{a.label}</span>
                    <span className="rounded-full bg-[var(--brand)] px-2 py-0.5 text-xs font-semibold text-white">
                      {a.n}
                    </span>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[var(--muted)]">Rien d'urgent — bon moment pour prospecter.</p>
            )}
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--muted)]">
              🎯 Objectif final
            </label>
            <textarea
              value={objectif}
              onChange={(e) => setObjectif(e.target.value)}
              rows={2}
              placeholder="Ex. 30 RDV qualifiés pour Rossini Energy d'ici fin du trimestre."
              className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
            />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--muted)]">
                👤 Client actif
              </label>
              <input
                value={client}
                onChange={(e) => setClient(e.target.value)}
                placeholder="Rossini Energy"
                className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--muted)]">
              📝 Récap / où on en est
            </label>
            <textarea
              value={resume}
              onChange={(e) => setResume(e.target.value)}
              rows={2}
              className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--muted)]">
              ⏰ Deadlines
            </label>
            <div className="space-y-2">
              {deadlines.map((d, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input
                    value={d.label}
                    onChange={(e) =>
                      setDeadlines((arr) =>
                        arr.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)),
                      )
                    }
                    placeholder="Jalon"
                    className="flex-1 rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm"
                  />
                  <input
                    type="date"
                    value={d.date}
                    onChange={(e) =>
                      setDeadlines((arr) =>
                        arr.map((x, j) => (j === i ? { ...x, date: e.target.value } : x)),
                      )
                    }
                    className="rounded-lg border border-[var(--border)] px-2 py-1.5 text-sm"
                  />
                  <button
                    onClick={() => setDeadlines((arr) => arr.filter((_, j) => j !== i))}
                    className="rounded-md px-2 py-1 text-xs text-red-600 hover:bg-red-50"
                  >
                    ✕
                  </button>
                </div>
              ))}
              <button
                onClick={() => setDeadlines((arr) => [...arr, { label: "", date: "" }])}
                className="rounded-lg border border-dashed border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--muted)] hover:bg-white"
              >
                + Ajouter une deadline
              </button>
            </div>
          </div>
          <button
            onClick={save}
            disabled={pending}
            className="rounded-lg bg-[var(--brand)] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40"
          >
            {pending ? "Enregistrement…" : "Enregistrer"}
          </button>
        </div>
      )}
    </div>
  );
}
