// Garde-fous de ciblage au lancement d'une recherche (charte agent-first :
// « propose → l'utilisateur valide »). Module PUR, sans dépendance : réutilisé
// par le formulaire (modale de validation) ET par le server action createRun
// (défense en profondeur si l'UI est contournée).

export type EffectifPresetId = "pme" | "petites" | "eti" | "custom";

export type EffectifPreset = {
  id: EffectifPresetId;
  label: string;
  hint: string;
  min: number | null;
  max: number | null;
};

// Bornes INSEE : la PME compte 10–250 salariés (cœur de cible Rossini). Les
// presets posent un min ET un max — un min seul, sans plafond, remontait des
// grands groupes hors cible (cf. consigne Paul : « effectif 100 → trop gros »).
export const EFFECTIF_PRESETS: readonly EffectifPreset[] = [
  { id: "pme", label: "PME", hint: "10–250 salariés (cœur de cible)", min: 10, max: 250 },
  { id: "petites", label: "Petites", hint: "10–49 salariés", min: 10, max: 49 },
  { id: "eti", label: "ETI", hint: "250–4999 salariés", min: 250, max: 4999 },
  { id: "custom", label: "Personnalisé", hint: "min / max libres", min: null, max: null },
] as const;

export const EFFECTIF_DEFAUT: EffectifPresetId = "pme";
export const EFFECTIF_MAX_ABSOLU = 50000;
export const VOLUME_MAX = 5000;

/** Preset par id (jamais undefined : retombe sur « personnalisé »). */
export function presetParId(id: EffectifPresetId): EffectifPreset {
  return EFFECTIF_PRESETS.find((p) => p.id === id) ?? EFFECTIF_PRESETS[3];
}

/** Devine le preset correspondant à un couple (min, max), sinon « custom ». */
export function presetPour(min: number | null, max: number | null): EffectifPresetId {
  const p = EFFECTIF_PRESETS.find(
    (x) => x.id !== "custom" && x.min === min && x.max === max,
  );
  return p ? p.id : "custom";
}

/** Libellé humain de la tranche d'effectif pour le récap de la modale. */
export function effectifLabel(min: number | null, max: number | null): string {
  if (min == null && max == null) return "Tous effectifs";
  if (min != null && max != null) return `${min}–${max} salariés`;
  if (min != null) return `≥ ${min} salariés (sans plafond)`;
  return `≤ ${max} salariés`;
}

export type CiblageInput = {
  effectifMin: number | null;
  effectifMax: number | null;
  volume: number | null;
  budgetEur: number | null;
  coutEstimeBas?: number | null; // estimation basse, pour l'alerte budget
  isTest?: boolean;
};

export type CiblageVerdict = {
  erreurs: string[]; // bloquant — on n'ouvre pas la modale / on refuse l'insert
  alertes: string[]; // non bloquant, dismissable — on prévient, l'utilisateur décide
};

/**
 * Valide (bloquant) et alerte (non bloquant) sur les paramètres de ciblage
 * avant lancement. Pas d'effet de bord : renvoie les deux listes de messages.
 */
export function validerCiblage(input: CiblageInput): CiblageVerdict {
  const erreurs: string[] = [];
  const alertes: string[] = [];
  const { effectifMin: min, effectifMax: max, volume, budgetEur, coutEstimeBas, isTest } =
    input;

  // --- Bloquant ---
  if (min != null && (min < 0 || min > EFFECTIF_MAX_ABSOLU))
    erreurs.push(`Effectif min. doit être entre 0 et ${EFFECTIF_MAX_ABSOLU}.`);
  if (max != null && (max < 0 || max > EFFECTIF_MAX_ABSOLU))
    erreurs.push(`Effectif max. doit être entre 0 et ${EFFECTIF_MAX_ABSOLU}.`);
  if (min != null && max != null && min > max)
    erreurs.push("Effectif min. supérieur à l'effectif max.");
  if (volume != null && (volume <= 0 || volume > VOLUME_MAX))
    erreurs.push(`Volume cible doit être entre 1 et ${VOLUME_MAX}.`);
  if (budgetEur != null && budgetEur < 0) erreurs.push("Budget plafond négatif.");

  // --- Alertes (agent-first : cœur de cible = PME 10–250) ---
  if (min != null && min >= 100)
    alertes.push(
      `Tu vises des entreprises ≥ ${min} salariés (ETI / grands groupes). ` +
        "Ton cœur de cible PME = 10–250 salariés.",
    );
  else if (max == null && (min ?? 0) >= 10)
    alertes.push(
      "Pas de plafond d'effectif : la recherche peut remonter de grandes " +
        "entreprises hors cœur de cible PME.",
    );
  if (
    !isTest &&
    budgetEur != null &&
    budgetEur > 0 &&
    coutEstimeBas != null &&
    coutEstimeBas > budgetEur
  )
    alertes.push(
      "Budget plafond sous l'estimation basse : le run pourrait s'arrêter " +
        "avant le volume visé.",
    );

  return { erreurs, alertes };
}
