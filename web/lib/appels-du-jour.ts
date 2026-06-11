// File d'appels du jour — « qui j'appelle aujourd'hui, et pourquoi ? ».
// Priorise le pipeline en une liste d'actions concrètes pour le matin :
// réponses chaudes d'abord, puis bascules téléphone, relances dues, et enfin
// les top leads jamais contactés. Helper pur (testé), rendu sur l'accueil.

import type { LeadStatus } from "@/lib/database.types";
import { potentielsScores } from "@/lib/ui";

export type LeadAppel = {
  id: string;
  entreprise: string;
  ville: string | null;
  statut: LeadStatus;
  score: number | null;
  contact_nom: string | null;
  contact_tel: string | null;
  relance_at: string | null;
  call_statut: string | null;
  score_raison: string | null;
  vision_satellite: Record<string, unknown> | null;
};

export type AppelDuJour = {
  lead: LeadAppel;
  priorite: 1 | 2 | 3 | 4;
  raison: string;
  angle: string | null;
};

const AXE_LABEL: Record<string, string> = {
  solaire: "solaire toiture",
  ombrieres: "ombrières parking",
  bornes: "bornes VE",
};

/** L'angle d'attaque en une phrase courte : meilleur potentiel v2, sinon le score_raison. */
export function anglePhrase(lead: Pick<LeadAppel, "vision_satellite" | "score_raison">): string | null {
  const p = potentielsScores(lead.vision_satellite);
  if (p.meilleur && p[p.meilleur] != null) {
    return `${AXE_LABEL[p.meilleur]} (${Math.round((p[p.meilleur] as number) / 10)}/10)`;
  }
  const raison = lead.score_raison?.trim();
  if (!raison) return null;
  return raison.length > 90 ? `${raison.slice(0, 87)}…` : raison;
}

export function fileAppelsDuJour(
  leads: LeadAppel[],
  now: Date = new Date(),
  max = 10,
): AppelDuJour[] {
  const endOfDay = new Date(now);
  endOfDay.setHours(23, 59, 59, 999);
  const horsJeu: LeadStatus[] = ["ecarte", "gagne", "perdu", "rdv_pris"];

  const file: AppelDuJour[] = [];
  for (const lead of leads) {
    if (horsJeu.includes(lead.statut)) continue;
    let priorite: AppelDuJour["priorite"] | null = null;
    let raison = "";

    if (lead.statut === "repondu") {
      priorite = 1;
      raison = "A répondu — bats le fer tant qu'il est chaud.";
    } else if (lead.call_statut === "a_appeler") {
      priorite = 2;
      raison = "Mail épuisé — l'agent propose de basculer au téléphone.";
    } else if (lead.relance_at && new Date(lead.relance_at) <= endOfDay) {
      priorite = 3;
      raison = "Relance due aujourd'hui.";
    } else if (
      (["nouveau", "a_valider", "valide"] as LeadStatus[]).includes(lead.statut) &&
      (lead.score ?? 0) >= 75
    ) {
      priorite = 4;
      raison = "Top lead jamais contacté — premier contact à fort potentiel.";
    }

    if (priorite == null) continue;
    file.push({ lead, priorite, raison, angle: anglePhrase(lead) });
  }

  file.sort(
    (a, b) => a.priorite - b.priorite || (b.lead.score ?? 0) - (a.lead.score ?? 0),
  );
  return file.slice(0, max);
}
