"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

const LINKS = [
  { href: "/inbox", label: "Prospects", icon: "👥" },
  { href: "/suivi", label: "Suivi", icon: "📊" },
  { href: "/campagnes", label: "Campagnes", icon: "✉️" },
  { href: "/veille", label: "Veille", icon: "🛰️" },
  { href: "/recherche", label: "Recherches", icon: "🔎" },
  { href: "/cibles", label: "Cibles", icon: "🎯" },
  { href: "/tableau-de-bord", label: "Tableau de bord", icon: "📈" },
  { href: "/agent", label: "Agent", icon: "🤖" },
  { href: "/mode-emploi", label: "Mode d'emploi", icon: "📖" },
];

// Sidebar gauche compacte (icônes) qui s'étend au survol pour révéler les
// libellés. Défile verticalement si trop d'entrées. N'encombre plus le haut.
export function Nav({ email }: { email: string | null }) {
  const pathname = usePathname();
  const router = useRouter();
  const [q, setQ] = useState("");

  function search(e: React.FormEvent) {
    e.preventDefault();
    const v = q.trim();
    if (v) router.push(`/inbox?q=${encodeURIComponent(v)}`);
  }

  return (
    <aside className="group fixed left-0 top-0 z-30 flex h-screen w-16 flex-col border-r border-[var(--border)] bg-white transition-[width] duration-200 ease-out hover:w-60 hover:shadow-xl">
      {/* Logo */}
      <Link
        href="/inbox"
        className="flex h-14 shrink-0 items-center gap-2 overflow-hidden px-4 text-[var(--brand)]"
      >
        <span className="text-xl">🧭</span>
        <span className="whitespace-nowrap text-lg font-bold opacity-0 transition-opacity duration-200 group-hover:opacity-100">
          ReSign CRM
        </span>
      </Link>

      {/* Recherche */}
      <form onSubmit={search} className="px-3 pb-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Rechercher…"
          className="w-full rounded-lg border border-[var(--border)] px-2 py-1.5 text-sm opacity-0 outline-none transition-opacity duration-200 focus:border-[var(--brand)] group-hover:opacity-100"
        />
      </form>

      {/* Liens (défilent si trop nombreux) */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-2 py-1">
        {LINKS.map((l) => {
          const active = pathname.startsWith(l.href);
          return (
            <Link
              key={l.href}
              href={l.href}
              title={l.label}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                active
                  ? "bg-[var(--brand)] text-white"
                  : "text-[var(--muted)] hover:bg-slate-100"
              }`}
            >
              <span className="w-5 shrink-0 text-center text-base leading-none">
                {l.icon}
              </span>
              <span className="whitespace-nowrap opacity-0 transition-opacity duration-200 group-hover:opacity-100">
                {l.label}
              </span>
            </Link>
          );
        })}
      </nav>

      {/* Bas : email + déconnexion */}
      <div className="shrink-0 border-t border-[var(--border)] p-3">
        <div className="mb-2 truncate text-xs text-[var(--muted)] opacity-0 transition-opacity duration-200 group-hover:opacity-100">
          {email}
        </div>
        <form action="/auth/signout" method="post">
          <button
            title="Déconnexion"
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-[var(--muted)] hover:bg-slate-100"
          >
            <span className="w-5 shrink-0 text-center leading-none">⏻</span>
            <span className="whitespace-nowrap opacity-0 transition-opacity duration-200 group-hover:opacity-100">
              Déconnexion
            </span>
          </button>
        </form>
      </div>
    </aside>
  );
}
