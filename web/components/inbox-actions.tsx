"use client";

import Link from "next/link";
import { logSuggestionClick } from "@/lib/actions/tracking";

export type InboxAction = { label: string; href: string; n: number; hint: string };

// Bande « Contexte → Actions » de l'onglet Prospects : l'onglet PROPOSE les
// prochaines actions (charte agent-first) au lieu de seulement lister. Les clics
// sont tracés (mesure de la valeur). Suit le pattern : Contexte → Actions → Données.
export function InboxActions({ actions }: { actions: InboxAction[] }) {
  const utiles = actions.filter((a) => a.n > 0);

  return (
    <div className="mb-5 rounded-2xl border border-[var(--brand)]/30 bg-gradient-to-br from-[var(--brand)]/5 to-transparent p-4">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
        🧭 Où on en est — prochaines actions
      </div>
      {utiles.length ? (
        <div className="flex flex-wrap gap-2">
          {utiles.map((a) => (
            <Link
              key={a.label}
              href={a.href}
              title={a.hint}
              onClick={() => void logSuggestionClick("inbox", a.label, a.href)}
              className="group flex items-center gap-2 rounded-xl border border-[var(--border)] bg-white px-3 py-2 text-sm hover:border-[var(--brand)] hover:shadow-sm"
            >
              <span className="font-medium group-hover:text-[var(--brand)]">{a.label}</span>
              <span className="rounded-full bg-[var(--brand)] px-2 py-0.5 text-xs font-semibold text-white">
                {a.n}
              </span>
            </Link>
          ))}
        </div>
      ) : (
        <p className="text-sm text-[var(--muted)]">
          Pipeline à jour — bon moment pour{" "}
          <Link href="/recherche" className="text-[var(--brand)] underline">
            lancer une recherche
          </Link>
          .
        </p>
      )}
    </div>
  );
}
