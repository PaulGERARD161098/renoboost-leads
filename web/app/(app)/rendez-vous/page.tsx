import Link from "next/link";
import { createClient } from "@/lib/supabase/server";

// Rendez-vous (PR3) — calendrier des RDV clients.
// Source : les leads passés en « RDV pris » (capté via le webhook Calendly, qui
// renseigne désormais `rdv_at`), classés par date. Résilient si la migration
// `rdv_at` n'est pas encore appliquée (repli sur une liste sans date).
export const dynamic = "force-dynamic";

type RdvRow = {
  id: string;
  entreprise: string;
  ville: string | null;
  contact_nom: string | null;
  rdv_at: string | null;
  updated_at: string;
};

const PARIS = "Europe/Paris";

function jourLabel(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR", {
    timeZone: PARIS,
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}
function heureLabel(iso: string): string {
  return new Date(iso).toLocaleTimeString("fr-FR", {
    timeZone: PARIS,
    hour: "2-digit",
    minute: "2-digit",
  });
}
function jourKey(iso: string): string {
  return new Intl.DateTimeFormat("fr-CA", { timeZone: PARIS }).format(new Date(iso));
}

export default async function RendezVousPage() {
  const supabase = await createClient();

  // Tente la requête datée ; repli si la colonne rdv_at n'existe pas encore.
  let rows: RdvRow[] = [];
  let colManquante = false;
  const dated = await supabase
    .from("leads")
    .select("id, entreprise, ville, contact_nom, rdv_at, updated_at")
    .eq("statut", "rdv_pris")
    .order("rdv_at", { ascending: true, nullsFirst: false })
    .limit(500);
  if (dated.error) {
    colManquante = true;
    const fallback = await supabase
      .from("leads")
      .select("id, entreprise, ville, contact_nom, updated_at")
      .eq("statut", "rdv_pris")
      .order("updated_at", { ascending: false })
      .limit(500);
    rows = ((fallback.data as Omit<RdvRow, "rdv_at">[]) ?? []).map((r) => ({
      ...r,
      rdv_at: null,
    }));
  } else {
    rows = (dated.data as RdvRow[]) ?? [];
  }

  const now = Date.now();
  const dateConnue = rows.filter((r) => r.rdv_at);
  const aVenir = dateConnue
    .filter((r) => new Date(r.rdv_at!).getTime() >= now - 3_600_000)
    .sort((a, b) => a.rdv_at!.localeCompare(b.rdv_at!));
  const passes = dateConnue
    .filter((r) => new Date(r.rdv_at!).getTime() < now - 3_600_000)
    .sort((a, b) => b.rdv_at!.localeCompare(a.rdv_at!));
  const sansDate = rows.filter((r) => !r.rdv_at);

  // Regroupe les RDV à venir par jour.
  const parJour = new Map<string, RdvRow[]>();
  for (const r of aVenir) {
    const k = jourKey(r.rdv_at!);
    (parJour.get(k) ?? parJour.set(k, []).get(k)!).push(r);
  }

  return (
    <div>
      <div className="mb-1 flex items-center gap-2">
        <span className="text-2xl">📅</span>
        <h1 className="text-2xl font-bold">Rendez-vous</h1>
      </div>
      <p className="mb-5 text-sm text-[var(--muted)]">
        Tes RDV clients, classés par date. Alimenté automatiquement quand un
        prospect réserve via Calendly.
      </p>

      {colManquante && (
        <div className="mb-5 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          ⏳ Les dates de RDV seront affichées dès que la migration{" "}
          <code>rdv_at</code> sera appliquée à la base. En attendant, voici les
          prospects ayant pris RDV.
        </div>
      )}

      {/* Contexte */}
      <div className="mb-5 grid grid-cols-3 gap-3">
        <Stat label="À venir" value={aVenir.length} />
        <Stat label="Passés" value={passes.length} />
        <Stat label="Sans date" value={sansDate.length} />
      </div>

      {/* À venir — groupé par jour */}
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
        ⚡ À venir
      </h2>
      {parJour.size === 0 ? (
        <div className="mb-6 rounded-xl border border-dashed border-[var(--border)] bg-white p-6 text-center text-sm text-[var(--muted)]">
          Aucun rendez-vous à venir.
        </div>
      ) : (
        <div className="mb-6 space-y-4">
          {[...parJour.entries()].map(([k, items]) => (
            <div key={k}>
              <div className="mb-1.5 text-sm font-semibold capitalize">
                {jourLabel(items[0].rdv_at!)}
              </div>
              <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-white">
                {items.map((r) => (
                  <RdvLigne key={r.id} r={r} heure={heureLabel(r.rdv_at!)} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Sans date (capté avant la migration, ou marqué à la main) */}
      {sansDate.length > 0 && (
        <>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            RDV pris — date non renseignée
          </h2>
          <div className="mb-6 overflow-hidden rounded-xl border border-[var(--border)] bg-white">
            {sansDate.map((r) => (
              <RdvLigne key={r.id} r={r} heure={null} />
            ))}
          </div>
        </>
      )}

      {/* Passés (repliés) */}
      {passes.length > 0 && (
        <details>
          <summary className="cursor-pointer text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            Passés ({passes.length})
          </summary>
          <div className="mt-2 overflow-hidden rounded-xl border border-[var(--border)] bg-white opacity-80">
            {passes.map((r) => (
              <RdvLigne
                key={r.id}
                r={r}
                heure={`${jourLabel(r.rdv_at!)} · ${heureLabel(r.rdv_at!)}`}
              />
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function RdvLigne({ r, heure }: { r: RdvRow; heure: string | null }) {
  return (
    <div className="flex items-center gap-3 border-b border-[var(--border)] px-4 py-2.5 last:border-0 hover:bg-slate-50">
      {heure && (
        <span className="shrink-0 rounded-md bg-[var(--brand)]/10 px-2 py-0.5 text-xs font-semibold text-[var(--brand)]">
          {heure}
        </span>
      )}
      <Link
        href={`/leads/${r.id}`}
        className="font-medium hover:text-[var(--brand)]"
      >
        {r.entreprise}
      </Link>
      <span className="text-sm text-[var(--muted)]">
        {r.contact_nom ? `· ${r.contact_nom}` : ""} {r.ville ? `· ${r.ville}` : ""}
      </span>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-white p-3 text-center">
      <div className="text-xl font-bold">{value}</div>
      <div className="text-xs text-[var(--muted)]">{label}</div>
    </div>
  );
}
