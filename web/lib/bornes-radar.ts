// Croisement « radar × potentiel » des bornes VE : le radar repère les
// départements SOUS-équipés (offre manquante) ; le potentiel, lui, vient de
// NOTRE pipeline — combien de prospects on a déjà sur ce territoire (demande
// identifiée). Un département sous-équipé OÙ l'on a déjà des prospects = priorité
// d'action (le marché est ouvert ET on y a un pied). Module pur, testable.

/**
 * Département (code INSEE) déduit d'un code postal français.
 * Gère la Corse (2A/2B selon le seuil 20200) et l'outre-mer (97x/98x).
 * Renvoie `null` si le code postal est vide ou non numérique.
 */
export function departementDeCodePostal(cp: string | null | undefined): string | null {
  if (!cp) return null;
  const digits = cp.trim().match(/^\d+/)?.[0];
  if (!digits) return null;
  const padded = digits.padStart(5, "0").slice(0, 5);
  if (padded.startsWith("97") || padded.startsWith("98")) return padded.slice(0, 3);
  if (padded.startsWith("20")) return Number(padded) < 20200 ? "2A" : "2B";
  return padded.slice(0, 2);
}

/** Compte les leads par département à partir de leurs codes postaux. */
export function tallyLeadsParDepartement(
  codesPostaux: (string | null | undefined)[],
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const cp of codesPostaux) {
    const dep = departementDeCodePostal(cp);
    if (!dep) continue;
    out[dep] = (out[dep] ?? 0) + 1;
  }
  return out;
}

export type LigneRadar = {
  departement: string;
  nom: string;
  pour100k: number;
  n: number;
  pipeline: number; // nb de prospects à nous dans ce département
  priorite: boolean; // sous-équipé ET pipeline > 0
};

/**
 * Croise les lignes du radar (densité bornes/hab) avec le pipeline. « Sous-équipé »
 * = densité sous la médiane des départements affichés. Tri : priorités d'abord
 * (pipeline décroissant), puis les plus sous-équipés. Garde les `limit` premiers.
 */
export function croiserRadarPotentiel(
  lignes: { departement: string; nom: string; pour100k: number; n: number }[],
  leadsParDept: Record<string, number>,
  limit = 12,
): LigneRadar[] {
  if (lignes.length === 0) return [];
  const densites = lignes.map((l) => l.pour100k).sort((a, b) => a - b);
  const mediane = densites[Math.floor(densites.length / 2)];

  return lignes
    .map((l) => {
      const pipeline = leadsParDept[l.departement] ?? 0;
      return {
        ...l,
        pipeline,
        priorite: l.pour100k <= mediane && pipeline > 0,
      };
    })
    .sort((a, b) => {
      if (a.priorite !== b.priorite) return a.priorite ? -1 : 1;
      if (a.priorite && b.priorite && b.pipeline !== a.pipeline) {
        return b.pipeline - a.pipeline;
      }
      return a.pour100k - b.pour100k; // sous-équipés d'abord
    })
    .slice(0, limit);
}
