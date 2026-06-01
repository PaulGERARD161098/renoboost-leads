"use client";

import { useState, useRef, useEffect } from "react";

type Message = { role: "user" | "assistant"; content: string };

const SUGGESTIONS = [
  "Lance une recherche pour moi",
  "Livre-moi les résultats de ma dernière recherche",
  "Compare mes 5 meilleurs leads",
  "Quels sont mes meilleurs départements ?",
  "Écris un cold mail pour mon top lead",
  "Par où je commence ?",
];

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
      setMessages((m) => [...m, { role: "assistant", content: reply }]);
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
        <div className="fixed bottom-24 right-5 z-40 flex h-[32rem] max-h-[calc(100vh-8rem)] w-[22rem] max-w-[calc(100vw-2.5rem)] flex-col overflow-hidden rounded-2xl border border-[var(--border)] bg-white shadow-2xl">
          <header className="border-b border-[var(--border)] bg-[var(--brand)] px-4 py-3 text-white">
            <div className="font-semibold">🧭 Magellan</div>
            <div className="text-xs opacity-80">
              Votre assistant de navigation commerciale
            </div>
          </header>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-3">
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
                  className={`inline-block max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm ${
                    m.role === "user"
                      ? "bg-[var(--brand)] text-white"
                      : "bg-slate-100 text-slate-800"
                  }`}
                >
                  {m.content}
                </div>
              </div>
            ))}
            {loading && (
              <div className="text-left">
                <div className="inline-block rounded-2xl bg-slate-100 px-3 py-2 text-sm text-[var(--muted)]">
                  …
                </div>
              </div>
            )}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex items-center gap-2 border-t border-[var(--border)] p-2"
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
              className="rounded-lg bg-[var(--brand)] px-3 py-2 text-sm font-medium text-white disabled:opacity-40"
            >
              Envoyer
            </button>
          </form>
        </div>
      )}
    </>
  );
}
