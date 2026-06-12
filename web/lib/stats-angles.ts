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

export type Angle = "solaire" | "ombrieres" | "bornes";

/** Libellés partagés (table /suivi, reco par cible, nudge fiche). */
export const ANGLE_LABEL: Record<Angle, string> = {
  solaire: "🔆 Solaire toiture",
  ombrieres: "🅿️ Ombrières",
  bornes: "🔌 Bornes VE",
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

// ──────────────────────────────────────────────────────────────────────────
// Angle gagnant PAR CIBLE — fermer la boucle d'apprentissage (charte agent-first)
// On ne se contente plus d'AFFICHER « quel discours convertit ? » globalement :
// par verticale (cible), on PROPOSE l'angle qui convertit le mieux, pour piloter
// les prochains brouillons. Propose → l'utilisateur valide en générant le mail.
// ──────────────────────────────────────────────────────────────────────────

export type LeadStatCible = LeadStat & { verticale_id: string | null };

export type AngleReco = {
  verticaleId: string;
  angle: Angle;
  envoyes: number;
  repondus: number;
  tauxReponse: number;
  gagnes: number;
  // Avance (points de %) sur le 2ᵉ meilleur angle de la cible — null si seul angle
  // ayant assez d'envois. Sert à doser la confiance de la reco.
  avance: number | null;
};

// Sous ce seuil d'envois, pas assez de signal pour recommander honnêtement un angle.
export const MIN_ENVOYES_RECO = 4;

/**
 * Pour chaque cible (verticale), l'angle qui convertit le mieux parmi ceux ayant
 * au moins `minEnvoyes` envois. Trié taux ↓, puis gagnés ↓, puis envoyés ↓.
 * Helper pur : la jointure id → nom de cible est faite côté page.
 */
export function angleGagnantParCible(
  leads: LeadStatCible[],
  minEnvoyes: number = MIN_ENVOYES_RECO,
): AngleReco[] {
  const groupes = new Map<string, LeadStatCible[]>();
  for (const l of leads) {
    if (!l.verticale_id) continue;
    const arr = groupes.get(l.verticale_id);
    if (arr) arr.push(l);
    else groupes.set(l.verticale_id, [l]);
  }

  const recos: AngleReco[] = [];
  for (const [verticaleId, groupe] of groupes) {
    const candidats = statsParAngle(groupe)
      .filter((s) => s.angle !== "sans_angle" && s.envoyes >= minEnvoyes)
      .sort(
        (a, b) =>
          (b.tauxReponse ?? 0) - (a.tauxReponse ?? 0) ||
          b.gagnes - a.gagnes ||
          b.envoyes - a.envoyes,
      );
    if (candidats.length === 0) continue;
    const gagnant = candidats[0];
    const second = candidats[1];
    recos.push({
      verticaleId,
      angle: gagnant.angle as Angle,
      envoyes: gagnant.envoyes,
      repondus: gagnant.repondus,
      tauxReponse: gagnant.tauxReponse ?? 0,
      gagnes: gagnant.gagnes,
      avance:
        second != null ? (gagnant.tauxReponse ?? 0) - (second.tauxReponse ?? 0) : null,
    });
  }
  return recos;
}
