// « Quel discours convertit ? » — agrège le tunnel par angle de mail
// (solaire / ombrières / bornes, persisté dans leads.mail_angle à la
// génération du brouillon). Helper pur, rendu sur /suivi.

import type { LeadStatus } from "@/lib/database.types";

export type LeadStat = {
  statut: LeadStatus;
  mail_angle: "solaire" | "ombrieres" | "bornes" | null;
  sent_at: string | null;
  replied_at: string | null;
  // Source de l'angle retenu — 'terrain' (analyse site) ou 'appris' (reco cible).
  // Optionnel : null/absent pour les anciens leads (hors A/B par source).
  mail_angle_source?: "terrain" | "appris" | null;
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
  // Auto-validée par les résultats : signal assez fort (volume + avance nette)
  // pour ne plus seulement « proposer » mais affirmer la reco. La boucle se
  // referme — la reco se valide elle-même sans intervention humaine.
  validee: boolean;
};

// Sous ce seuil d'envois, pas assez de signal pour recommander honnêtement un angle.
export const MIN_ENVOYES_RECO = 4;

// Auto-validation : une reco devient « validée par les résultats » quand le signal
// est solide — assez d'envois sur l'angle gagnant ET avance nette sur le 2ᵉ angle
// (un comparant existe et le départage est franc, pas du bruit).
export const MIN_ENVOYES_VALID = 8;
export const MIN_AVANCE_VALID = 15; // points de %

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
    const avance =
      second != null ? (gagnant.tauxReponse ?? 0) - (second.tauxReponse ?? 0) : null;
    recos.push({
      verticaleId,
      angle: gagnant.angle as Angle,
      envoyes: gagnant.envoyes,
      repondus: gagnant.repondus,
      tauxReponse: gagnant.tauxReponse ?? 0,
      gagnes: gagnant.gagnes,
      avance,
      validee:
        gagnant.envoyes >= MIN_ENVOYES_VALID &&
        avance != null &&
        avance >= MIN_AVANCE_VALID,
    });
  }
  return recos;
}

export type LiftAngleAppris = {
  aligne: { envoyes: number; repondus: number; taux: number };
  autre: { envoyes: number; repondus: number; taux: number };
  lift: number; // écart de taux de réponse (points de %), aligné − autre
};

/**
 * Mesure de la valeur (charte) : sur les cibles qui ont un angle gagnant fiable,
 * compare le taux de réponse des leads dont l'angle envoyé COÏNCIDE avec l'angle
 * appris vs les autres. Renvoie null tant qu'on n'a pas les deux côtés (pas de
 * comparant honnête). Helper pur, rendu sur /suivi.
 */
export function liftAngleAppris(
  leads: LeadStatCible[],
  minEnvoyes: number = MIN_ENVOYES_RECO,
): LiftAngleAppris | null {
  const best = new Map(
    angleGagnantParCible(leads, minEnvoyes).map((r) => [r.verticaleId, r.angle]),
  );
  if (best.size === 0) return null;

  let aE = 0,
    aR = 0,
    oE = 0,
    oR = 0;
  for (const l of leads) {
    if (!l.verticale_id || l.mail_angle == null) continue;
    const b = best.get(l.verticale_id);
    if (!b) continue; // cible sans angle gagnant fiable : hors mesure
    const envoye = l.sent_at != null || CONTACTES.includes(l.statut);
    if (!envoye) continue;
    const repondu = l.replied_at != null || A_REPONDU.includes(l.statut);
    if (l.mail_angle === b) {
      aE++;
      if (repondu) aR++;
    } else {
      oE++;
      if (repondu) oR++;
    }
  }
  if (aE === 0 || oE === 0) return null;
  const taux = (r: number, e: number) => Math.round((r / e) * 100);
  return {
    aligne: { envoyes: aE, repondus: aR, taux: taux(aR, aE) },
    autre: { envoyes: oE, repondus: oR, taux: taux(oR, oE) },
    lift: taux(aR, aE) - taux(oR, oE),
  };
}

export type LiftAngleSource = {
  terrain: { envoyes: number; repondus: number; taux: number };
  appris: { envoyes: number; repondus: number; taux: number };
  // Écart de taux de réponse (points de %), terrain − appris. Positif = le
  // terrain (analyse site) convertit mieux que l'angle appris ; négatif = c'est
  // l'inverse, et la règle « le terrain prime toujours » mérite d'être réexaminée.
  ecart: number;
};

/**
 * A/B « terrain vs appris » (charte : mesurer la valeur). On suppose aujourd'hui
 * que l'angle terrain prime toujours sur l'angle appris ; ce helper le MESURE en
 * comparant le taux de réponse selon la SOURCE de l'angle réellement utilisé
 * (persistée à la génération du brouillon). Renvoie null tant qu'un des deux côtés
 * manque (pas de comparant honnête). Helper pur, rendu sur /suivi.
 */
export function liftAngleSource(leads: LeadStat[]): LiftAngleSource | null {
  let tE = 0,
    tR = 0,
    aE = 0,
    aR = 0;
  for (const l of leads) {
    const src = l.mail_angle_source;
    if (src !== "terrain" && src !== "appris") continue;
    const envoye = l.sent_at != null || CONTACTES.includes(l.statut);
    if (!envoye) continue;
    const repondu = l.replied_at != null || A_REPONDU.includes(l.statut);
    if (src === "terrain") {
      tE++;
      if (repondu) tR++;
    } else {
      aE++;
      if (repondu) aR++;
    }
  }
  if (tE === 0 || aE === 0) return null;
  const taux = (r: number, e: number) => Math.round((r / e) * 100);
  return {
    terrain: { envoyes: tE, repondus: tR, taux: taux(tR, tE) },
    appris: { envoyes: aE, repondus: aR, taux: taux(aR, aE) },
    ecart: taux(tR, tE) - taux(aR, aE),
  };
}
