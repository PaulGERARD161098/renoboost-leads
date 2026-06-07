import type { SupabaseClient } from "@supabase/supabase-js";
import type { Lead, Run, RunStatus } from "@/lib/database.types";
import { zoneLabel } from "@/lib/ui";

export type RunReportEntreprise = {
  entreprise: string;
  ville: string | null;
  score: number | null;
  email: boolean;
  tel: boolean;
  horsFiltre: boolean;
};

export type RunReport = {
  runId: string;
  titre: string;
  cibleNom: string;
  statut: RunStatus;
  createdAt: string;
  finishedAt: string | null;
  dureeS: number | null;
  coutTotal: number;
  coutDetail: Record<string, number>;
  coutParLead: number | null;
  coutParQualifie: number | null;
  perimetre: {
    zone: string;
    effectifMin: number | null;
    volumeCible: number | null;
    budgetEur: number | null;
    cible: string;
  };
  counts: { total: number; qualifies: number; horsFiltre: number; top: number };
  taux: { email: number; contactNom: number; tel: number } | null;
  scoreMoyen: number | null;
  entreprises: RunReportEntreprise[];
};

function pct(n: number, total: number): number {
  return total > 0 ? Math.round((100 * n) / total) : 0;
}

/**
 * Assemble le rapport de fin de recherche d'un run : coûts, temps, périmètre
 * précis et entreprises ciblées. Calculé côté serveur, consommé par la modale.
 */
export async function getRunReport(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  supabase: SupabaseClient<any, any, any>,
  runId: string,
): Promise<RunReport | null> {
  const { data: runData } = await supabase
    .from("runs")
    .select("*")
    .eq("id", runId)
    .maybeSingle();
  const run = runData as Run | null;
  if (!run) return null;

  let cible = "—";
  if (run.verticale_id) {
    const { data: v } = await supabase
      .from("verticales")
      .select("nom")
      .eq("id", run.verticale_id)
      .maybeSingle();
    cible = (v as { nom: string } | null)?.nom ?? "—";
  }

  const { data: leadsData } = await supabase
    .from("leads")
    .select("entreprise, ville, score, contact_email, contact_tel, contact_nom, hors_filtre")
    .eq("run_id", runId)
    .order("score", { ascending: false, nullsFirst: false })
    .limit(500);
  type L = Pick<
    Lead,
    "entreprise" | "ville" | "score" | "contact_email" | "contact_tel" | "contact_nom" | "hors_filtre"
  >;
  const leads = (leadsData as L[] | null) ?? [];

  const emailOk = (e: string | null) => !!e && e.trim() !== "";
  const qualifies = leads.filter((l) => !l.hors_filtre);
  const horsFiltre = leads.length - qualifies.length;
  const top = leads.filter((l) => (l.score ?? 0) >= 75).length;

  const taux =
    qualifies.length > 0
      ? {
          email: pct(qualifies.filter((l) => emailOk(l.contact_email)).length, qualifies.length),
          contactNom: pct(
            qualifies.filter((l) => !!l.contact_nom && l.contact_nom.trim() !== "").length,
            qualifies.length,
          ),
          tel: pct(qualifies.filter((l) => emailOk(l.contact_tel)).length, qualifies.length),
        }
      : null;

  const scoresQ = qualifies.map((l) => l.score ?? 0);
  const scoreMoyen =
    scoresQ.length > 0 ? Math.round((scoresQ.reduce((a, b) => a + b, 0) / scoresQ.length) * 10) / 10 : null;

  // Durée : du lancement à la dernière mise à jour (finalisation) si le run est
  // terminé/échoué ; sinon temps écoulé jusqu'à maintenant.
  const start = new Date(run.created_at).getTime();
  const end =
    run.status === "termine" || run.status === "echoue"
      ? new Date(run.updated_at).getTime()
      : Date.now();
  const dureeS = Number.isFinite(start) && Number.isFinite(end) ? Math.max(0, Math.round((end - start) / 1000)) : null;

  const cout = Number(run.cout_eur) || 0;
  const coutDetail =
    run.cout_detail && typeof run.cout_detail === "object"
      ? (run.cout_detail as Record<string, number>)
      : {};
  const zone = run.zone as { effectif_min?: number | null } | undefined;

  return {
    runId: run.id,
    titre: run.nom || cible,
    cibleNom: cible,
    statut: run.status,
    createdAt: run.created_at,
    finishedAt: run.status === "termine" || run.status === "echoue" ? run.updated_at : null,
    dureeS,
    coutTotal: cout,
    coutDetail,
    coutParLead: leads.length > 0 ? Math.round((cout / leads.length) * 100) / 100 : null,
    coutParQualifie: qualifies.length > 0 ? Math.round((cout / qualifies.length) * 100) / 100 : null,
    perimetre: {
      zone: zoneLabel(run.zone),
      effectifMin: zone?.effectif_min ?? null,
      volumeCible: run.volume_cible,
      budgetEur: run.budget_eur,
      cible,
    },
    counts: { total: leads.length, qualifies: qualifies.length, horsFiltre, top },
    taux,
    scoreMoyen,
    entreprises: leads.slice(0, 100).map((l) => ({
      entreprise: l.entreprise,
      ville: l.ville,
      score: l.score,
      email: emailOk(l.contact_email),
      tel: emailOk(l.contact_tel),
      horsFiltre: l.hors_filtre,
    })),
  };
}

/** Formate une durée en secondes → « 4 min 12 s » / « 1 h 03 ». */
export function formatDuree(s: number | null): string {
  if (s == null) return "—";
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  const sec = s % 60;
  if (m < 60) return `${m} min${sec ? ` ${sec.toString().padStart(2, "0")} s` : ""}`;
  const h = Math.floor(m / 60);
  return `${h} h ${(m % 60).toString().padStart(2, "0")}`;
}
