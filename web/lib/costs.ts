// Coûts d'un run, côté UI — estimation (avant lancement) ET ventilation réelle
// par API (après le run, alimentée par le worker via `runs.cout_detail`).
//
// Ratios indicatifs par lead, alignés sur .env.example / COSTS_AND_LIMITS.md :
//   - Étage 1 (Google Places)        ~0,05 €/lead  (overhead grille inclus)
//   - Étage 2 (data.gouv)             gratuit ; Pappers seulement en fallback
//                                     (~0,08 €/lead enrichi) si la clé est posée
//   - Étage 3 (scraping)              gratuit
//   - Étage 3.5 (Dropcontact, option) ~0,10 €/lead enrichi
//   - Étage 4 (Claude, scoring+pitch) ~0,005 €/lead (Haiku) → ~0,02 €/lead (Sonnet)
//
// On expose une fourchette basse/haute par API pour rester honnête : le coût réel
// dépend du modèle Claude et de l'activation des enrichissements Pappers/Dropcontact.

export const COUT_PLACES_PAR_LEAD = 0.05;
export const COUT_PAPPERS_PAR_LEAD = 0.08;
export const COUT_DROPCONTACT_PAR_LEAD = 0.1;
export const COUT_CLAUDE_HAIKU_PAR_LEAD = 0.005;
export const COUT_CLAUDE_SONNET_PAR_LEAD = 0.02;

// Une pré-rédaction de relance = une génération Claude Sonnet (~700 tokens),
// du même ordre qu'un pitch d'étage 4. Sert à chiffrer le coût IA des relances.
export const COUT_RELANCE_PREDRAFT_EUR = COUT_CLAUDE_SONNET_PAR_LEAD;

/** Coût IA estimé de `nb` pré-rédactions de relance. */
export function coutRelances(nb: number): number {
  return Math.max(0, nb) * COUT_RELANCE_PREDRAFT_EUR;
}

/**
 * Nombre de pré-rédactions encore permises sous le plafond de coût du jour
 * (garde-fou budget). `coutMaxJour` ≤ 0 → pas de plafond (Infinity).
 */
export function predraftsRestantsSousBudget(
  coutMaxJour: number,
  dejaRedigeesAujourdhui: number,
): number {
  if (!(coutMaxJour > 0)) return Infinity;
  const restantEur = coutMaxJour - coutRelances(dejaRedigeesAujourdhui);
  return Math.max(0, Math.floor(restantEur / COUT_RELANCE_PREDRAFT_EUR));
}

/** Les 4 postes de coût pilotés (les 3 API payantes + Claude). */
export type CoutCategorie = "places" | "pappers" | "dropcontact" | "claude";

export type CoutCategorieInfo = {
  cle: CoutCategorie;
  label: string;
  detail: string;
  /** Classe Tailwind pour la pastille de couleur du badge. */
  couleur: string;
};

/** Ordre canonique d'affichage (suit le pipeline L1 → L4). */
export const COUT_CATEGORIES: CoutCategorieInfo[] = [
  {
    cle: "places",
    label: "Google Places",
    detail: "Découverte des établissements (étage 1)",
    couleur: "bg-sky-500",
  },
  {
    cle: "pappers",
    label: "Pappers",
    detail: "Données entreprise — fallback (étage 2)",
    couleur: "bg-amber-500",
  },
  {
    cle: "dropcontact",
    label: "Dropcontact",
    detail: "Enrichissement contact (étage 3.5)",
    couleur: "bg-violet-500",
  },
  {
    cle: "claude",
    label: "Claude",
    detail: "Scoring + rédaction des mails (étage 4)",
    couleur: "bg-emerald-500",
  },
];

const CATEGORIE_PAR_CLE: Record<CoutCategorie, CoutCategorieInfo> =
  Object.fromEntries(COUT_CATEGORIES.map((c) => [c.cle, c])) as Record<
    CoutCategorie,
    CoutCategorieInfo
  >;

// €/lead par API, fourchette [bas, haut]. Pappers/Dropcontact = 0 en bas car
// optionnels (activés seulement si la clé API correspondante est configurée).
const RATIOS_PAR_LEAD: Record<CoutCategorie, { bas: number; haut: number }> = {
  places: { bas: COUT_PLACES_PAR_LEAD, haut: COUT_PLACES_PAR_LEAD },
  pappers: { bas: 0, haut: COUT_PAPPERS_PAR_LEAD },
  dropcontact: { bas: 0, haut: COUT_DROPCONTACT_PAR_LEAD },
  claude: { bas: COUT_CLAUDE_HAIKU_PAR_LEAD, haut: COUT_CLAUDE_SONNET_PAR_LEAD },
};

export type EstimationCout = {
  bas: number; // Places + Claude Haiku, sans enrichissement
  haut: number; // Places + Pappers + Dropcontact + Claude Sonnet
};

export type LigneEstimation = CoutCategorieInfo & { bas: number; haut: number };

/** Estime le coût d'un run, ventilé par API (fourchette basse/haute par poste). */
export function estimerCoutDetail(volumeCible: number): LigneEstimation[] {
  const v = Number.isFinite(volumeCible) && volumeCible > 0 ? volumeCible : 0;
  return COUT_CATEGORIES.map((c) => ({
    ...c,
    bas: v * RATIOS_PAR_LEAD[c.cle].bas,
    haut: v * RATIOS_PAR_LEAD[c.cle].haut,
  }));
}

/** Estime le coût total d'un run (fourchette basse/haute), tous postes confondus. */
export function estimerCoutRun(volumeCible: number): EstimationCout {
  return estimerCoutDetail(volumeCible).reduce(
    (acc, l) => ({ bas: acc.bas + l.bas, haut: acc.haut + l.haut }),
    { bas: 0, haut: 0 },
  );
}

export type LigneCout = CoutCategorieInfo & { montant: number };

/**
 * Normalise une ventilation réelle (`runs.cout_detail`, jsonb) en lignes prêtes
 * à afficher : ordre canonique, libellés, postes à 0 € écartés. Tolère un objet
 * absent/partiel ou des clés inconnues (ignorées).
 */
export function normaliserCoutDetail(
  detail: Record<string, number> | null | undefined,
): LigneCout[] {
  if (!detail || typeof detail !== "object") return [];
  const lignes: LigneCout[] = [];
  for (const c of COUT_CATEGORIES) {
    const montant = Number(detail[c.cle]);
    if (Number.isFinite(montant) && montant > 0) {
      lignes.push({ ...c, montant });
    }
  }
  return lignes;
}

/** Somme d'une ventilation réelle (postes connus uniquement). */
export function sommeCoutDetail(
  detail: Record<string, number> | null | undefined,
): number {
  return normaliserCoutDetail(detail).reduce((s, l) => s + l.montant, 0);
}

/** Agrège plusieurs ventilations (cumul tous runs) en un seul objet par poste. */
export function cumulerCoutDetail(
  details: (Record<string, number> | null | undefined)[],
): Record<CoutCategorie, number> {
  const total = { places: 0, pappers: 0, dropcontact: 0, claude: 0 };
  for (const d of details) {
    if (!d || typeof d !== "object") continue;
    for (const c of COUT_CATEGORIES) {
      const m = Number(d[c.cle]);
      if (Number.isFinite(m) && m > 0) total[c.cle] += m;
    }
  }
  return total;
}

/** Métadonnées d'un poste de coût (label, couleur) par clé. */
export function categorieInfo(cle: CoutCategorie): CoutCategorieInfo {
  return CATEGORIE_PAR_CLE[cle];
}

/** Formate un montant € avec 0 ou 2 décimales selon l'ordre de grandeur. */
export function formatEur(montant: number): string {
  if (!Number.isFinite(montant)) return "—";
  const decimales = montant >= 10 ? 0 : montant >= 1 ? 1 : 2;
  return `${montant.toFixed(decimales)} €`;
}
