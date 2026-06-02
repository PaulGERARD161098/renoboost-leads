"use client";

import { useState, useRef, useEffect } from "react";
import { Markdown } from "@/components/markdown";

type Message = { role: "user" | "assistant"; content: string; steps?: string[] };

const SUGGESTIONS = [
  "Lance une recherche pour moi",
  "Livre-moi les résultats de ma dernière recherche",
  "Compare mes 5 meilleurs leads",
  "Quels sont mes meilleurs départements ?",
  "Analyse le potentiel solaire de mon top lead",
  "Par où je commence ?",
];

// Libellés lisibles des outils, pour montrer "où on en est".
const STEP_LABEL: Record<string, string> = {
  compter_leads: "État des lieux",
  lister_leads: "Lecture des leads",
  detail_lead: "Fiche du lead",
  lister_runs: "Recherches récentes",
  stats_recherches: "Perf. des recherches",
  stats_departements: "Perf. par département",
  meilleures_zones: "Meilleures zones",
  lister_zones_cibles: "Zones enregistrées",
  lister_cibles: "Cibles actives",
  lancer_recherche: "Lancement d'une recherche",
  resultats_recherche: "Résultats d'une recherche",
  statut_agent: "État de l'agent",
  analyser_satellite: "Analyse satellite",
};

export function AssistantWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, loading]);

  async function send(text: string) {
    const content = text.trim();
    if (!content || loading) return;
    const next = [...messages, { role: "user" as const, content }];
    setMessages(next);
    setInput("");
    setLoading(true);
    try {
      const res = await fetch("/api/assistant", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ messages: next }),
      });
      const data = await res.json();
      const reply =
        data.reply ??
        data.error ??
        "Une erreur est survenue. Réessaie dans un instant.";
      setMessages((m) => [
        ...m,
        { role: "assistant", content: reply, steps: data.steps },
      ]);
    } catch {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: "Connexion impossible. Vérifie ta connexion et réessaie.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {/* Bouton flottant */}
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Magellan — assistant de navigation"
        className="fixed bottom-5 right-5 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-[var(--brand)] text-2xl text-white shadow-lg transition hover:scale-105"
      >
        {open ? <span className="leading-none">×</span> : <span>🧭</span>}
      </button>

      {/* Panneau */}
      {open && (
        <div className="fixed bottom-24 right-5 z-40 flex h-[40rem] max-h-[calc(100vh-7rem)] w-[34rem] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-2xl border border-[var(--border)] bg-white shadow-2xl">
          <header className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--brand)] px-4 py-3 text-white">
            <div>
              <div className="font-semibold">🧭 Magellan</div>
              <div className="text-xs opacity-80">
                Votre assistant de navigation commerciale
              </div>
            </div>
            {messages.length > 0 && (
              <button
                onClick={() => setMessages([])}
                className="rounded-md px-2 py-1 text-xs text-white/90 hover:bg-white/15"
              >
                Effacer
              </button>
            )}
          </header>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
            {messages.length === 0 && (
              <div className="space-y-3">
                <p className="text-sm text-[var(--muted)]">
                  Pose-moi une question sur l&apos;outil ou tes prospects.
                </p>
                <div className="flex flex-wrap gap-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      className="rounded-full border border-[var(--border)] px-3 py-1 text-xs text-[var(--muted)] hover:bg-slate-100"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={m.role === "user" ? "text-right" : "text-left"}
              >
                <div
                  className={`inline-block max-w-[88%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                    m.role === "user"
                      ? "whitespace-pre-wrap bg-[var(--brand)] text-white"
                      : "bg-slate-100 text-slate-800"
                  }`}
                >
                  {m.role === "user" ? m.content : <Markdown text={m.content} />}
                </div>
                {m.role === "assistant" && m.steps && m.steps.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {m.steps.map((s, j) => (
                      <span
                        key={j}
                        className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] text-[var(--muted)]"
                      >
                        🔧 {STEP_LABEL[s] ?? s}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="text-left">
                <div className="inline-flex items-center gap-2 rounded-2xl bg-slate-100 px-3.5 py-2.5 text-sm text-[var(--muted)]">
                  <span className="flex gap-1">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--brand)] [animation-delay:-0.3s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--brand)] [animation-delay:-0.15s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--brand)]" />
                  </span>
                  Magellan travaille…
                </div>
              </div>
            )}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex items-center gap-2 border-t border-[var(--border)] p-3"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Écris ta question…"
              className="flex-1 rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
            >
              Envoyer
            </button>
          </form>
        </div>
      )}
    </>
  );
}
