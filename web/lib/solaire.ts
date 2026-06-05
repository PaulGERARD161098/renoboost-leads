// Estimation « ordre de grandeur » du potentiel solaire d'un site, dérivée des
// surfaces détectées sur la vue aérienne (analyse IGN + IA, cf. lib/satellite.ts
// et solaireFromVision dans lib/outreach.ts).
//
// ⚠️ Ce sont des ESTIMATIONS commerciales prudentes, jamais des mesures
// certifiées : on part de surfaces déjà estimées, et on arrondit toujours en
// ordre de grandeur. Constantes volontairement conservatrices et documentées.

// Part réellement exploitable d'une toiture (ombres, équipements, accès, marges).
const RATIO_TOITURE_UTILE = 0.65;
// Densité de pose en toiture : ~6 m² de toiture par kWc installé.
const M2_PAR_KWC_TOITURE = 6;
// Part d'un parking réellement couvrable par des ombrières.
const RATIO_PARKING_UTILE = 0.5;
// Ombrières : pose moins dense que la toiture (structure, circulation).
const M2_PAR_KWC_OMBRIERE = 10;
// Productible moyen en France (kWh/an par kWc), prudent (réf. ~900 nord → 1300 sud).
const KWH_PAR_KWC_AN = 1050;
// Valorisation prudente du kWh (autoconsommation/revente, mix indicatif).
const EUR_PAR_KWH = 0.11;

export type SolaireSurfaces = {
  toiture_m2: number | null;
  parking_m2: number | null;
  ombrieres: boolean | null;
};

export type SolaireEstimation = {
  kwc: number;
  productionKwhAn: number;
  caAnnuelEur: number;
  toitureKwc: number;
  ombriereKwc: number;
};

// Arrondi à l'unité `pas` la plus proche (ordre de grandeur).
function arrondi(v: number, pas: number): number {
  return Math.round(v / pas) * pas;
}

/**
 * Estime puissance (kWc), production annuelle (kWh/an) et CA annuel indicatif (€)
 * à partir des surfaces détectées. Renvoie null si rien d'exploitable.
 */
export function estimerSolaire(s: SolaireSurfaces): SolaireEstimation | null {
  const toiture = s.toiture_m2 && s.toiture_m2 > 0 ? s.toiture_m2 : 0;
  const parking = s.ombrieres && s.parking_m2 && s.parking_m2 > 0 ? s.parking_m2 : 0;

  const toitureKwcBrut = (toiture * RATIO_TOITURE_UTILE) / M2_PAR_KWC_TOITURE;
  const ombriereKwcBrut = (parking * RATIO_PARKING_UTILE) / M2_PAR_KWC_OMBRIERE;
  const kwcBrut = toitureKwcBrut + ombriereKwcBrut;
  if (kwcBrut < 1) return null;

  // Arrondis en ordre de grandeur : kWc au plus proche de 5, production au
  // millier de kWh, CA aux 500 €.
  const kwc = arrondi(kwcBrut, 5);
  const productionKwhAn = arrondi(kwcBrut * KWH_PAR_KWC_AN, 1000);
  const caAnnuelEur = arrondi(kwcBrut * KWH_PAR_KWC_AN * EUR_PAR_KWH, 500);

  return {
    kwc: Math.max(5, kwc),
    productionKwhAn,
    caAnnuelEur,
    toitureKwc: arrondi(toitureKwcBrut, 5),
    ombriereKwc: arrondi(ombriereKwcBrut, 5),
  };
}

/** Formatage court FR pour l'affichage (ex. « ~120 kWc », « ~12 500 €/an »). */
export function fmtKwc(kwc: number): string {
  return `~${kwc.toLocaleString("fr-FR")} kWc`;
}
export function fmtKwh(kwh: number): string {
  return `~${kwh.toLocaleString("fr-FR")} kWh/an`;
}
export function fmtEur(eur: number): string {
  return `~${eur.toLocaleString("fr-FR")} €/an`;
}
