import Link from "next/link";
import type { AppelDuJour } from "@/lib/appels-du-jour";
import { LEAD_STATUS_COLOR, LEAD_STATUS_LABEL } from "@/lib/ui";

const PRIORITE_DOT: Record<number, string> = {
  1: "bg-red-500",
  2: "bg-orange-500",
  3: "bg-amber-400",
  4: "bg-emerald-500",
};

/**
 * « Qui j'appelle aujourd'hui ? » — la liste du matin du commercial, rendue
 * sur l'accueil : chaque ligne dit pourquoi maintenant + l'angle d'attaque,
 * avec le téléphone cliquable quand on l'a.
 */
export function AppelsDuJour({ file }: { file: AppelDuJour[] }) {
  if (file.length === 0) return null;

  return (
    <section className="mb-5 rounded-2xl border border-[var(--border)] bg-white p-5">
      <div className="mb-3 flex items-end justify-between">
        <div>
          <h2 className="text-base font-bold">📞 File d&apos;appels du jour</h2>
          <p className="text-xs text-[var(--muted)]">
            Les {file.length} contacts à travailler en priorité ce matin — et pourquoi.
          </p>
        </div>
        <Link href="/suivi" className="text-sm font-medium text-[var(--brand)] hover:underline">
          Pipeline complet →
        </Link>
      </div>

      <ol className="divide-y divide-[var(--border)]">
        {file.map((a, i) => (
          <li key={a.lead.id} className="flex items-center gap-3 py-2.5">
            <span className="w-5 shrink-0 text-right text-sm font-bold text-[var(--muted)]">
              {i + 1}
            </span>
            <span
              className={`h-2.5 w-2.5 shrink-0 rounded-full ${PRIORITE_DOT[a.priorite]}`}
              title={`Priorité ${a.priorite}`}
            />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  href={`/leads/${a.lead.id}`}
                  className="truncate text-sm font-semibold hover:text-[var(--brand)] hover:underline"
                >
                  {a.lead.entreprise}
                </Link>
                {a.lead.ville && (
                  <span className="text-xs text-[var(--muted)]">{a.lead.ville}</span>
                )}
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${LEAD_STATUS_COLOR[a.lead.statut]}`}
                >
                  {LEAD_STATUS_LABEL[a.lead.statut]}
                </span>
              </div>
              <p className="truncate text-xs text-[var(--muted)]">
                {a.raison}
                {a.angle && <> · Angle : {a.angle}</>}
              </p>
            </div>
            {a.lead.contact_tel ? (
              <a
                href={`tel:${a.lead.contact_tel.replace(/\s/g, "")}`}
                className="shrink-0 rounded-lg bg-[var(--brand)] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[var(--brand-dark)]"
              >
                📞 {a.lead.contact_tel}
              </a>
            ) : (
              <Link
                href={`/leads/${a.lead.id}`}
                className="shrink-0 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--muted)] hover:bg-slate-50"
                title="Pas de téléphone — ouvrir la fiche pour enrichir le contact"
              >
                Fiche →
              </Link>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
