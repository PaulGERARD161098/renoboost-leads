import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { TourneeBoard } from "@/components/tournee-board";
import {
  CATEGORIE_META,
  opportunitesAutourDesRdv,
  pointsTournee,
  type LeadCarto,
} from "@/lib/tournees";

export const dynamic = "force-dynamic";

// Carte des tournées (charte agent-first) : transforme les trous d'agenda en
// visites. Contexte (où sont mes affaires) → Actions (profite d'un RDV pour
// voir les prospects du coin) → Données (la carte).
export default async function TourneesPage() {
  const supabase = await createClient();
  const { data } = await supabase
    .from("leads")
    .select("id, entreprise, ville, statut, score, latitude, longitude, rdv_at, contact_tel")
    .not("latitude", "is", null)
    .order("score", { ascending: false, nullsFirst: false })
    .limit(1000);

  const points = pointsTournee((data as LeadCarto[] | null) ?? []);
  const opportunites = opportunitesAutourDesRdv(points, 20);

  const compte = (c: "rdv" | "chaud" | "tiede") =>
    points.filter((p) => p.categorie === c).length;

  return (
    <div>
      <div className="mb-5">
        <h1 className="text-2xl font-bold">🗺️ Tournées</h1>
        <p className="text-sm text-[var(--muted)]">
          Où sont tes affaires sur la carte — et comment grouper tes
          déplacements pour rentabiliser chaque sortie.
        </p>
      </div>

      {points.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-white p-8 text-center text-sm text-[var(--muted)]">
          Aucun prospect géolocalisé à visiter pour l&apos;instant. Les leads
          analysés (avec coordonnées) et tes RDV apparaîtront ici.
        </div>
      ) : (
        <>
          {/* ── Contexte : combien d'affaires sur le terrain ── */}
          <div className="mb-5 grid grid-cols-3 gap-3">
            {(["rdv", "chaud", "tiede"] as const).map((c) => (
              <div key={c} className="rounded-xl border border-[var(--border)] bg-white p-4">
                <div className="text-2xl font-bold" style={{ color: CATEGORIE_META[c].color }}>
                  {compte(c)}
                </div>
                <div className="text-xs text-[var(--muted)]">
                  {CATEGORIE_META[c].emoji} {CATEGORIE_META[c].label}
                </div>
              </div>
            ))}
          </div>

          {/* ── Actions recommandées : grouper autour des RDV ── */}
          {opportunites.length > 0 && (
            <div className="mb-5 rounded-2xl border border-[var(--brand)]/30 bg-[var(--brand)]/5 p-4">
              <h2 className="mb-2 text-sm font-bold">
                💡 Profite de tes RDV pour prospecter le coin
              </h2>
              <ul className="space-y-2">
                {opportunites.map((o) => (
                  <li key={o.rdv.lead.id} className="text-sm">
                    <span className="font-medium">📅 {o.rdv.lead.entreprise}</span>
                    {o.rdv.lead.ville && (
                      <span className="text-[var(--muted)]"> ({o.rdv.lead.ville})</span>
                    )}
                    {" — "}
                    <span className="text-[var(--brand)]">
                      {o.aProximite.length} prospect{o.aProximite.length > 1 ? "s" : ""} à moins de 20 km
                    </span>
                    {" : "}
                    <span className="text-[var(--muted)]">
                      {o.aProximite
                        .slice(0, 4)
                        .map((p) => p.lead.entreprise)
                        .join(", ")}
                      {o.aProximite.length > 4 ? "…" : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* ── Données + itinéraire : la carte et l'ordre des visites ── */}
          <TourneeBoard points={points} />

          <p className="mt-3 text-xs text-[var(--muted)]">
            Astuce : un prospect n&apos;apparaît que s&apos;il a été géolocalisé
            (analyse satellite ou import avec adresse).{" "}
            <Link href="/inbox" className="underline">
              Voir tous les prospects →
            </Link>
          </p>
        </>
      )}
    </div>
  );
}
