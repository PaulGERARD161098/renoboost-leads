"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/inbox", label: "Prospects" },
  { href: "/suivi", label: "Suivi" },
  { href: "/recherche", label: "Nouvelle recherche" },
  { href: "/cibles", label: "Cibles" },
  { href: "/mode-emploi", label: "Mode d'emploi" },
];

export function Nav({ email }: { email: string | null }) {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-10 border-b border-[var(--border)] bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-6">
          <Link href="/inbox" className="text-lg font-bold text-[var(--brand)]">
            ReSign CRM
          </Link>
          <nav className="flex gap-1">
            {LINKS.map((l) => {
              const active = pathname.startsWith(l.href);
              return (
                <Link
                  key={l.href}
                  href={l.href}
                  className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
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
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden text-sm text-[var(--muted)] sm:inline">
            {email}
          </span>
          <form action="/auth/signout" method="post">
            <button className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm font-medium hover:bg-slate-100">
              Déconnexion
            </button>
          </form>
        </div>
      </div>
    </header>
  );
}
