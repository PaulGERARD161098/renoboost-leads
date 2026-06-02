"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

const LINKS = [
  { href: "/inbox", label: "Prospects" },
  { href: "/suivi", label: "Suivi" },
  { href: "/recherche", label: "Recherches" },
  { href: "/cibles", label: "Cibles" },
  { href: "/tableau-de-bord", label: "Tableau de bord" },
  { href: "/agent", label: "Agent" },
  { href: "/mode-emploi", label: "Mode d'emploi" },
];

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
    <header className="sticky top-0 z-10 border-b border-[var(--border)] bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
        <Link href="/inbox" className="text-lg font-bold text-[var(--brand)]">
          ReSign CRM
        </Link>

        <nav className="order-3 flex w-full gap-1 overflow-x-auto md:order-none md:w-auto">
          {LINKS.map((l) => {
            const active = pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`shrink-0 whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                  active
                    ? "bg-[var(--brand)] text-white"
                    : "text-[var(--muted)] hover:bg-slate-100"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>

        <form onSubmit={search} className="ml-auto">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Rechercher un lead…"
            className="w-36 rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm outline-none focus:border-[var(--brand)] sm:w-44"
          />
        </form>

        <span className="hidden text-sm text-[var(--muted)] lg:inline">
          {email}
        </span>
        <form action="/auth/signout" method="post">
          <button className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm font-medium hover:bg-slate-100">
            Déconnexion
          </button>
        </form>
      </div>
    </header>
  );
}
