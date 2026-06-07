import Link from "next/link";
import type { VeilleSignal } from "@/lib/database.types";
import { estSignalVE } from "@/lib/veille-signaux";

// Bloc « Signaux de veille liés » de la fiche lead (interconnexion veille → lead).
// Tracabilité : d'où vient ce lead, et quels signaux d'achat le portent. Les
// signaux VE (flotte/IRVE/électrification) sont marqués — ils nourrissent aussi
// le potentiel bornes à l'analyse satellite.

const TYPE_LABEL: Record<string, string> = {
  ve_flotte: "Flotte VE",
  irve: "Bornes / IRVE",
  electrification: "Électrification",
  ombrieres: "Ombrières",
  autre: "Autre",
};

export function SignauxVeLies({ signaux }: { signaux: VeilleSignal[] }) {
  if (signaux.length === 0) return null;

  return (
    <div className="rounded-xl border border-[var(--border)] bg-white p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold">🛰️ Signaux de veille liés</h3>
        <Link href="/veille" className="text-xs text-[var(--brand)] hover:underline">
          Voir la veille →
        </Link>
      </div>
      <ul className="space-y-2">
        {signaux.map((s) => {
          const ve = estSignalVE(s);
          return (
            <li
              key={s.id}
              className="rounded-lg border border-[var(--border)] bg-slate-50 px-3 py-2"
            >
              <div className="flex flex-wrap items-center gap-1.5">
                <span
                  className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                    ve ? "bg-[var(--brand)]/10 text-[var(--brand)]" : "bg-slate-200 text-slate-600"
                  }`}
                >
                  {ve ? "🔌 " : ""}
                  {TYPE_LABEL[s.type ?? "autre"] ?? s.type}
                </span>
                {typeof s.score_intention === "number" && (
                  <span className="text-xs text-[var(--muted)]">
                    intention {s.score_intention}/100
                  </span>
                )}
              </div>
              {s.declencheur && (
                <p className="mt-1 text-sm text-slate-700">{s.declencheur}</p>
              )}
              {s.angle && (
                <p className="mt-0.5 text-xs italic text-[var(--muted)]">↳ {s.angle}</p>
              )}
              {s.source_url && (
                <a
                  href={s.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-0.5 inline-block text-xs text-[var(--brand)] hover:underline"
                >
                  Source ↗
                </a>
              )}
            </li>
          );
        })}
      </ul>
      {signaux.some(estSignalVE) && (
        <p className="mt-2 text-xs text-[var(--muted)]">
          🔌 Signal VE détecté → le potentiel bornes est rehaussé à l&apos;analyse aérienne.
        </p>
      )}
    </div>
  );
}
