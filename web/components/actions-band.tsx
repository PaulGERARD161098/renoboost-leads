"use client";

import Link from "next/link";
import { logSuggestionClick } from "@/lib/actions/tracking";

export type BandAction = { label: string; href: string; n: number; hint: string };

// Bande « Contexte → Actions » réutilisable sur chaque onglet (charte agent-first) :
// l'onglet PROPOSE les prochaines actions au lieu de seulement afficher des
// données. Les clics sont tracés par `source` (mesure de la valeur).
export function ActionsBand({
  source,
  actions,
  title = "🧭 Où on en est — prochaines actions",
  emptyHref = "/recherche",
  emptyLabel = "lancer une recherche",
}: {
  source: string;
  actions: BandAction[];
  title?: string;
  emptyHref?: string;
  emptyLabel?: string;
}) {
  const utiles = actions.filter((a) => a.n > 0);

  return (
    <div className="mb-5 rounded-2xl border border-[var(--brand)]/30 bg-gradient-to-br from-[var(--brand)]/5 to-transparent p-4">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
        {title}
      </div>
      {utiles.length ? (
        <div className="flex flex-wrap gap-2">
          {utiles.map((a) => (
            <Link
              key={a.label}
              href={a.href}
              title={a.hint}
              onClick={() => void logSuggestionClick(source, a.label, a.href)}
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
          Rien d&apos;urgent —{" "}
          <Link href={emptyHref} className="text-[var(--brand)] underline">
            {emptyLabel}
          </Link>
          .
        </p>
      )}
    </div>
  );
}
