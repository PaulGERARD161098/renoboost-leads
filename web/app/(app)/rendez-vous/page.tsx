import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import type { Lead } from "@/lib/database.types";

// Rendez-vous — vue d'amorce (PR1). Liste les prospects passés en « RDV pris »
// (source interne). Le vrai calendrier (source Calendly live + repli interne)
// arrive en PR3 ; cet écran sert déjà de point d'entrée depuis l'accueil.
export const dynamic = "force-dynamic";

export default async function RendezVousPage() {
  const supabase = await createClient();
  const { data } = await supabase
    .from("leads")
    .select("id, entreprise, ville, contact_nom, updated_at")
    .eq("statut", "rdv_pris")
    .order("updated_at", { ascending: false })
    .limit(200);
  const leads = (data as Partial<Lead>[]) ?? [];

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">📅 Rendez-vous</h1>
      <p className="mb-5 text-sm text-[var(--muted)]">
        Tes RDV clients. Le calendrier complet (synchronisé Calendly) arrive
        bientôt — voici déjà les prospects passés en « RDV pris ».
      </p>

      {leads.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-white p-8 text-center text-sm text-[var(--muted)]">
          Aucun rendez-vous pour l&apos;instant. Dès qu&apos;un prospect prend
          RDV, il apparaîtra ici.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs text-[var(--muted)]">
              <tr>
                <th className="px-4 py-2 font-medium">Entreprise</th>
                <th className="px-4 py-2 font-medium">Contact</th>
                <th className="px-4 py-2 font-medium">Ville</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((l) => (
                <tr
                  key={l.id}
                  className="border-t border-[var(--border)] hover:bg-slate-50"
                >
                  <td className="px-4 py-2.5">
                    <Link
                      href={`/leads/${l.id}`}
                      className="font-medium hover:text-[var(--brand)]"
                    >
                      {l.entreprise}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 text-[var(--muted)]">
                    {l.contact_nom ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 text-[var(--muted)]">
                    {l.ville ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
