"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { Briefing } from "@/lib/briefing";
import { markSessionSeen } from "@/lib/actions/session";
import { genererResumeSession } from "@/lib/actions/context";
import { logSuggestionClick } from "@/lib/actions/tracking";

// Modale d'accueil « reprise au login » (charte agent-first) : salutation
// nominative + date, ce qui est nouveau depuis la dernière session, et les
// priorités du jour cliquables. S'affiche une fois par jour, dismissable.
export function WelcomeModal({ briefing }: { briefing: Briefing }) {
  const router = useRouter();
  const [open, setOpen] = useState(true);
  const [resume, setResume] = useState(briefing.resume);
  const [resumeLoading, setResumeLoading] = useState(briefing.resumeStale);

  // Affichée = session vue : on horodate pour ne pas la rejouer aujourd'hui.
  // Et si le récap est périmé, on le (re)génère automatiquement au login.
  useEffect(() => {
    void markSessionSeen();
    if (briefing.resumeStale) {
      genererResumeSession()
        .then((res) => {
          if (res && "resume" in res && res.resume) setResume(res.resume);
        })
        .finally(() => setResumeLoading(false));
    }
  }, [briefing.resumeStale]);

  if (!open) return null;

  function close() {
    setOpen(false);
  }

  function go(href: string, action: string) {
    void logSuggestionClick("welcome_modal", action, href);
    setOpen(false);
    router.push(href);
  }

  const { prenom, dateLabel, objectif, nouveautes, priorites } = briefing;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 backdrop-blur-sm sm:items-center"
      onClick={close}
    >
      <div
        className="my-auto w-full max-w-2xl rounded-2xl border border-[var(--border)] bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* En-tête : salutation + date */}
        <div className="flex items-start justify-between gap-3 rounded-t-2xl bg-gradient-to-br from-[var(--brand)]/10 to-transparent px-6 pb-4 pt-5">
          <div>
            <h2 className="text-xl font-bold">Bonjour {prenom} 👋</h2>
            <p className="mt-0.5 text-sm capitalize text-[var(--muted)]">{dateLabel}</p>
            {objectif && (
              <p className="mt-2 text-sm">
                <span className="text-[var(--muted)]">🎯 Objectif : </span>
                {objectif}
              </p>
            )}
          </div>
          <button
            onClick={close}
            aria-label="Fermer"
            className="shrink-0 rounded-lg px-2 py-1 text-lg text-[var(--muted)] hover:bg-white/70"
          >
            ✕
          </button>
        </div>

        <div className="space-y-5 px-6 py-5">
          {/* Cartouche 1 — Quoi de neuf */}
          <section>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
              📣 Quoi de neuf depuis la dernière fois
            </h3>
            {resumeLoading ? (
              <p className="mb-2 rounded-lg bg-slate-50 px-3 py-2 text-sm italic text-[var(--muted)]">
                ✨ Magellan résume la dernière session…
              </p>
            ) : (
              resume && (
                <p className="mb-2 rounded-lg bg-slate-50 px-3 py-2 text-sm leading-relaxed text-slate-700">
                  📝 {resume}
                </p>
              )
            )}
            {nouveautes.length ? (
              <ul className="space-y-1.5">
                {nouveautes.map((n, i) => (
                  <li key={i}>
                    <button
                      onClick={() => go(n.href, n.text)}
                      className="flex w-full items-center gap-2 rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-left text-sm hover:border-[var(--brand)] hover:bg-slate-50"
                    >
                      <span className="shrink-0">{n.icon}</span>
                      <span className="flex-1">{n.text}</span>
                      <span className="shrink-0 text-[var(--brand)]">→</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-[var(--muted)]">
                Rien de neuf depuis ta dernière session. Bon moment pour prospecter.
              </p>
            )}
          </section>

          {/* Cartouche 2 — On fait quoi aujourd'hui */}
          <section>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
              ⚡ On fait quoi aujourd'hui ?
            </h3>
            {priorites.length ? (
              <div className="grid gap-2 sm:grid-cols-2">
                {priorites.map((p) => (
                  <button
                    key={p.label}
                    onClick={() => go(p.href, p.label)}
                    className="group flex flex-col rounded-xl border border-[var(--border)] bg-white p-3 text-left hover:border-[var(--brand)] hover:shadow-sm"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold group-hover:text-[var(--brand)]">
                        {p.label}
                      </span>
                      <span className="shrink-0 rounded-full bg-[var(--brand)] px-2 py-0.5 text-xs font-semibold text-white">
                        {p.n}
                      </span>
                    </div>
                    <span className="mt-1 text-xs text-[var(--muted)]">{p.hint}</span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[var(--muted)]">
                Aucune action urgente. Lance une recherche pour alimenter le pipeline.
              </p>
            )}
          </section>
        </div>

        {/* Pied : accès libre à l'outil */}
        <div className="flex items-center justify-between gap-2 rounded-b-2xl border-t border-[var(--border)] bg-slate-50 px-6 py-3">
          <span className="text-xs text-[var(--muted)]">
            Choisis une priorité, ou explore librement.
          </span>
          <button
            onClick={close}
            className="rounded-lg border border-[var(--border)] bg-white px-4 py-1.5 text-sm font-medium hover:bg-slate-50"
          >
            Accéder à l'outil →
          </button>
        </div>
      </div>
    </div>
  );
}
