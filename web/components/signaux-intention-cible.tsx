import Link from "next/link";
import type { VeilleSignal } from "@/lib/database.types";

// Bloc « Signaux d'intention réels » de la fiche Cible (interconnexion
// intentions ⟶ veille). Là où les presets d'intention donnent un proxy NAF, ce
// bloc remonte les entreprises qui prouvent l'intention sur le terrain (flotte
// VE immatriculée, projet ombrières détecté…). Lecture seule : la conversion en
// lead se fait dans la Veille (bouton « En faire un lead »).

const TYPE_LABEL: Record<string, string> = {
  ve_flotte: "Flotte VE",
  irve: "Bornes / IRVE",
  electrification: "Électrification",
  ombrieres: "Ombrières",
  autre: "Autre",
};

export function SignauxIntentionCible({ signaux }: { signaux: VeilleSignal[] }) {
  return (
    <div className="mt-6 rounded-xl border border-[var(--border)] bg-white p-6">
      <div className="mb-1 flex items-center justify-between">
        <h2 className="text-sm font-semibold">🛰️ Signaux d&apos;intention réels</h2>
        <Link href="/veille" className="text-xs text-[var(--brand)] hover:underline">
          Voir la veille →
        </Link>
      </div>
      <p className="mb-3 text-xs text-[var(--muted)]">
        Entreprises qui montrent l&apos;intention sur le terrain (vs le proxy
        sectoriel ci-dessus). Convertis-les en prospect depuis la Veille.
      </p>

      {signaux.length === 0 ? (
        <p className="rounded-lg border border-dashed border-[var(--border)] bg-slate-50 px-3 py-4 text-sm text-[var(--muted)]">
          Aucun signal pour l&apos;instant. Coche une intention à signal direct
          (flotte VE, conso élec) puis lance la veille pour en détecter.
        </p>
      ) : (
        <ul className="space-y-2">
          {signaux.map((s) => (
            <li
              key={s.id}
              className="rounded-lg border border-[var(--border)] bg-slate-50 px-3 py-2"
            >
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="rounded bg-[var(--brand)]/10 px-1.5 py-0.5 text-xs font-medium text-[var(--brand)]">
                  {TYPE_LABEL[s.type ?? "autre"] ?? s.type}
                </span>
                <span className="text-sm font-medium">{s.entreprise}</span>
                {s.ville && (
                  <span className="text-xs text-[var(--muted)]">· {s.ville}</span>
                )}
                {typeof s.score_intention === "number" && (
                  <span className="ml-auto text-xs text-[var(--muted)]">
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
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
