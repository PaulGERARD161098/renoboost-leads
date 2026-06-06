"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { logRetour } from "@/lib/actions/feedback";
import { isFeedbackEnd } from "@/lib/feedback";

const STORE_KEY = "leads_henry_retour"; // "open" | "done"

// Pop-up de retours d'Henry : monté dans le layout → il le SUIT sur toutes les
// pages (survit aux changements de route). Henry consigne ses retours en vrac ;
// ils s'empilent dans `retours` (Claude les draine). Il tape « fin du retour »
// pour clore : le pop-up disparaît alors définitivement.
export function FeedbackDock() {
  const pathname = usePathname();
  const [ready, setReady] = useState(false); // évite le flash SSR/hydratation
  const [active, setActive] = useState(false); // session de retours en cours
  const [open, setOpen] = useState(false); // panneau déplié
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [entries, setEntries] = useState<string[]>([]);
  const [ended, setEnded] = useState(false);
  const taRef = useRef<HTMLTextAreaElement>(null);

  // État initial (localStorage) + ouverture forcée à la fin de la cinématique V1.
  useEffect(() => {
    let state: string | null = null;
    try {
      state = localStorage.getItem(STORE_KEY);
    } catch {
      /* localStorage indisponible */
    }
    if (state !== "done") setActive(true);
    setReady(true);

    function onOpen() {
      setActive(true);
      setOpen(true);
    }
    window.addEventListener("leads:retour-open", onOpen);
    return () => window.removeEventListener("leads:retour-open", onOpen);
  }, []);

  useEffect(() => {
    if (open) taRef.current?.focus();
  }, [open]);

  function clore() {
    try {
      localStorage.setItem(STORE_KEY, "done");
    } catch {
      /* no-op */
    }
    setEnded(true);
    setOpen(false);
    // Petit message de remerciement avant disparition complète.
    setTimeout(() => setActive(false), 4000);
  }

  async function submit() {
    const texte = input.trim();
    if (!texte || sending) return;

    // Commande de clôture : « fin du retour ».
    if (isFeedbackEnd(texte)) {
      setInput("");
      clore();
      return;
    }

    setSending(true);
    try {
      const res = await logRetour({
        source: "henry_popup",
        texte,
        page: pathname,
      });
      if (res && "ok" in res) {
        setEntries((e) => [texte, ...e].slice(0, 8));
        setInput("");
      }
    } finally {
      setSending(false);
      taRef.current?.focus();
    }
  }

  if (!ready || !active) {
    // Message de remerciement éphémère à la clôture.
    if (ended) {
      return (
        <div className="fixed bottom-5 left-5 z-40 max-w-xs rounded-2xl border border-[var(--border)] bg-white px-4 py-3 text-sm shadow-xl">
          ✅ Merci Henry ! Tes retours sont transmis à Paul & Claude. On regarde
          tout ça. 🙌
        </div>
      );
    }
    return null;
  }

  return (
    <>
      {/* Lanceur flottant (bas-gauche, pour ne pas chevaucher Magellan) */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-5 left-5 z-40 flex items-center gap-2 rounded-full bg-amber-500 px-4 py-3 text-sm font-semibold text-white shadow-lg transition hover:scale-105"
        >
          📝 Donner mon retour
          {entries.length > 0 && (
            <span className="rounded-full bg-white/25 px-2 py-0.5 text-xs">
              {entries.length}
            </span>
          )}
        </button>
      )}

      {/* Panneau */}
      {open && (
        <div className="fixed bottom-5 left-5 z-40 flex max-h-[calc(100vh-2.5rem)] w-[22rem] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-2xl border border-[var(--border)] bg-white shadow-2xl">
          <header className="flex items-start justify-between gap-2 bg-amber-500 px-4 py-3 text-white">
            <div>
              <div className="text-sm font-semibold">📝 Tes retours, Henry</div>
              <div className="text-xs opacity-90">
                En vrac, autant que tu veux — ça part direct à Paul & Claude.
              </div>
            </div>
            <button
              onClick={() => setOpen(false)}
              aria-label="Réduire"
              className="rounded-md px-2 py-1 text-lg leading-none text-white/90 hover:bg-white/15"
            >
              –
            </button>
          </header>

          {entries.length > 0 && (
            <div className="max-h-40 space-y-1.5 overflow-y-auto border-b border-[var(--border)] bg-slate-50 p-3">
              {entries.map((e, i) => (
                <div
                  key={i}
                  className="rounded-lg bg-white px-2.5 py-1.5 text-xs text-slate-700 shadow-sm"
                >
                  ✅ {e}
                </div>
              ))}
            </div>
          )}

          <div className="p-3">
            <textarea
              ref={taRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  void submit();
                }
              }}
              rows={3}
              placeholder="Ce qui te plaît, ce qui cloche, une idée… (page courante jointe automatiquement)"
              className="w-full resize-none rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-amber-500"
            />
            <div className="mt-2 flex items-center justify-between gap-2">
              <button
                onClick={clore}
                className="rounded-lg px-2.5 py-1.5 text-xs font-medium text-[var(--muted)] hover:bg-slate-100"
                title="Équivaut à écrire « fin du retour »"
              >
                Fin du retour
              </button>
              <button
                onClick={() => void submit()}
                disabled={sending || !input.trim()}
                className="rounded-lg bg-amber-500 px-4 py-1.5 text-sm font-semibold text-white disabled:opacity-40"
              >
                {sending ? "Envoi…" : "Envoyer"}
              </button>
            </div>
            <p className="mt-2 text-[11px] leading-snug text-[var(--muted)]">
              Tape <strong>« fin du retour »</strong> (ou le bouton) quand tu as
              tout dit — ce pop-up disparaîtra alors.
            </p>
          </div>
        </div>
      )}
    </>
  );
}
