import { createClient } from "@/lib/supabase/server";
import type { Lead } from "@/lib/database.types";
import { solaireFromVision } from "@/lib/outreach";
import { estimerSolaire } from "@/lib/solaire";
import { potentielsScores } from "@/lib/ui";
import { SolaireWorkspace, type SolaireLead } from "@/components/solaire-workspace";

// Workspace ☀️ Solaire — domaine à part entière (charte agent-first).
// Pattern Contexte → Actions recommandées → Données : on classe tous les leads
// par potentiel solaire, on propose l'analyse par lot + la génération d'approche,
// et on chiffre (kWc / production / CA) en ordre de grandeur.
export const dynamic = "force-dynamic";

type Row = Pick<
  Lead,
  | "id"
  | "entreprise"
  | "ville"
  | "code_postal"
  | "adresse"
  | "statut"
  | "score"
  | "latitude"
  | "longitude"
  | "vision_satellite"
>;

export default async function SolairePage() {
  const supabase = await createClient();
  const { data } = await supabase
    .from("leads")
    .select(
      "id, entreprise, ville, code_postal, adresse, statut, score, latitude, longitude, vision_satellite",
    )
    .limit(5000);
  const rows = (data as Row[]) ?? [];

  const leads: SolaireLead[] = rows.map((l) => {
    const vision = l.vision_satellite as Record<string, unknown> | null;
    // Les 3 sous-scores /100 (solaire toiture / ombrières / bornes) + axe gagnant.
    const pot = potentielsScores(vision);
    const surfaces = solaireFromVision(vision);
    const estim = surfaces ? estimerSolaire(surfaces) : null;
    // Analysable si on a de quoi localiser (coordonnées, adresse ou ville).
    const canAnalyse =
      (typeof l.latitude === "number" && typeof l.longitude === "number") ||
      Boolean(l.adresse?.trim()) ||
      Boolean(l.ville?.trim());

    return {
      id: l.id,
      entreprise: l.entreprise,
      ville: l.ville,
      codePostal: l.code_postal,
      statut: l.statut,
      scoreCommercial: typeof l.score === "number" ? l.score : null,
      scoreSolaire: pot.solaire,
      scoreOmbrieres: pot.ombrieres,
      scoreBornes: pot.bornes,
      meilleur: pot.meilleur,
      latitude: typeof l.latitude === "number" ? l.latitude : null,
      longitude: typeof l.longitude === "number" ? l.longitude : null,
      analyse: vision != null,
      canAnalyse,
      toitureM2: surfaces?.toiture_m2 ?? null,
      parkingM2: surfaces?.parking_m2 ?? null,
      ombrieres: surfaces?.ombrieres ?? null,
      kwc: estim?.kwc ?? null,
      productionKwhAn: estim?.productionKwhAn ?? null,
      caAnnuelEur: estim?.caAnnuelEur ?? null,
    };
  });

  return (
    <div>
      <div className="mb-1 flex items-center gap-2">
        <span className="text-2xl">☀️</span>
        <h1 className="text-2xl font-bold">Solaire</h1>
      </div>
      <p className="mb-5 text-sm text-[var(--muted)]">
        Le potentiel de ton portefeuille sur les 3 axes Rossini — ☀️ toiture,
        🅿️ ombrières, 🔌 bornes VE — détectés par vue aérienne, notés, chiffrés
        et prêts à transformer en approche commerciale.
      </p>

      <SolaireWorkspace leads={leads} />
    </div>
  );
}
