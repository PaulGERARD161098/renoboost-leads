"use client";

import { useState } from "react";
import type { LeadMessage } from "@/lib/database.types";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const SOURCE_LABEL: Record<string, string> = {
  manuel: "manuel",
  instantly: "Instantly",
  systeme: "simulation",
};

// Fil de conversation type Outlook : nos envois (droite) et les réponses du
// prospect (gauche), dépliable en un badge compact.
export function MailThread({ messages }: { messages: LeadMessage[] }) {
  const [ouvert, setOuvert] = useState(true);
  const nbRecus = messages.filter((m) => m.direction === "in").length;

  return (
    <div className="rounded-xl border border-[var(--border)] bg-white p-5">
      <button
        onClick={() => setOuvert((v) => !v)}
        className="mb-1 flex w-full items-center justify-between"
      >
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
          Conversation
          <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium normal-case text-[var(--muted)]">
            {messages.length} message{messages.length > 1 ? "s" : ""}
            {nbRecus > 0 ? ` · ${nbRecus} reçu${nbRecus > 1 ? "s" : ""}` : ""}
          </span>
        </h2>
        <span className="text-xs text-[var(--muted)]">{ouvert ? "▾" : "▸"}</span>
      </button>

      {ouvert &&
        (messages.length === 0 ? (
          <p className="mt-2 text-sm text-[var(--muted)]">
            Aucun échange pour l’instant. Le fil se remplit dès le premier envoi
            et à chaque réponse du prospect.
          </p>
        ) : (
          <ul className="mt-3 space-y-3">
            {messages.map((m) => {
              const sortant = m.direction === "out";
              return (
                <li
                  key={m.id}
                  className={`flex ${sortant ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
                      sortant
                        ? "rounded-br-sm bg-[var(--accent,#2563eb)] text-white"
                        : "rounded-bl-sm bg-slate-100 text-slate-800"
                    }`}
                  >
                    <div
                      className={`mb-1 flex items-center gap-2 text-xs ${
                        sortant ? "text-blue-100" : "text-[var(--muted)]"
                      }`}
                    >
                      <span className="font-medium">
                        {sortant ? "Nous" : "Prospect"}
                      </span>
                      <span>· {formatDate(m.at)}</span>
                      <span>· {SOURCE_LABEL[m.source] ?? m.source}</span>
                    </div>
                    {m.sujet && <p className="font-medium">{m.sujet}</p>}
                    {m.corps ? (
                      <p className="whitespace-pre-wrap leading-relaxed">{m.corps}</p>
                    ) : (
                      <p
                        className={`italic ${sortant ? "text-blue-100" : "text-[var(--muted)]"}`}
                      >
                        (corps non disponible)
                      </p>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        ))}
    </div>
  );
}
