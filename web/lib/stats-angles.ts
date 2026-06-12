// « Quel discours convertit ? » — agrège le tunnel par angle de mail
// (solaire / ombrières / bornes, persisté dans leads.mail_angle à la
// génération du brouillon). Helper pur, rendu sur /suivi.

import type { LeadStatus } from "@/lib/database.types";

export type LeadStat = {
  statut: LeadStatus;
  mail_angle: "solaire" | "ombrieres" | "bornes" | null;
  sent_at: string | null;
  replied_at: string | null;
};

export type AngleStat = {
  angle: "solaire" | "ombrieres" | "bornes" | "sans_angle";
  envoyes: number;
  repondus: number;
  tauxReponse: number | null; // % arrondi, null si rien d'envoyé
  gagnes: number;
};

const CONTACTES: LeadStatus[] = [
  "envoye",
  "ouvert",
  "repondu",
  "a_relancer",
  "rdv_pris",
  "gagne",
  "perdu",
];
const A_REPONDU: LeadStatus[] = ["repondu", "rdv_pris", "gagne", "perdu"];

/** Stats par angle, triées par taux de réponse décroissant (sans_angle en dernier). */
export function statsParAngle(leads: LeadStat[]): AngleStat[] {
  const init = (angle: AngleStat["angle"]): AngleStat => ({
    angle,
    envoyes: 0,
    repondus: 0,
    tauxReponse: null,
    gagnes: 0,
  });
  const byAngle: Record<AngleStat["angle"], AngleStat> = {
    solaire: init("solaire"),
    ombrieres: init("ombrieres"),
    bornes: init("bornes"),
    sans_angle: init("sans_angle"),
  };

  for (const l of leads) {
    const envoye = l.sent_at != null || CONTACTES.includes(l.statut);
    if (!envoye) continue;
    const stat = byAngle[l.mail_angle ?? "sans_angle"];
    stat.envoyes++;
    if (l.replied_at != null || A_REPONDU.includes(l.statut)) stat.repondus++;
    if (l.statut === "gagne") stat.gagnes++;
  }

  const rows = Object.values(byAngle).filter((s) => s.envoyes > 0);
  for (const s of rows) s.tauxReponse = Math.round((s.repondus / s.envoyes) * 100);
  rows.sort((a, b) => {
    if (a.angle === "sans_angle") return 1;
    if (b.angle === "sans_angle") return -1;
    return (b.tauxReponse ?? 0) - (a.tauxReponse ?? 0);
  });
  return rows;
}
