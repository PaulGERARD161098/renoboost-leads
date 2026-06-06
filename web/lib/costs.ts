// Estimation de coût d'un run, côté UI (garde-fou budget avant lancement).
//
// Ratios indicatifs par lead, alignés sur .env.example / COSTS_AND_LIMITS.md :
//   - Étage 1 (Google Places)        ~0,05 €/lead  (overhead grille inclus)
//   - Étage 2 (data.gouv)             gratuit
//   - Étage 3 (scraping)              gratuit
//   - Étage 4 (Claude, scoring+pitch) ~0,005 €/lead (Haiku) → ~0,02 €/lead (Sonnet)
//   - Étage 3.5 (Dropcontact, option) ~0,10 €/lead enrichi
//
// On expose une fourchette basse/haute pour rester honnête : le coût réel dépend
// du modèle Claude et de l'activation de l'enrichissement Dropcontact.

export const COUT_PLACES_PAR_LEAD = 0.05;
export const COUT_CLAUDE_HAIKU_PAR_LEAD = 0.005;
export const COUT_CLAUDE_SONNET_PAR_LEAD = 0.02;
export const COUT_DROPCONTACT_PAR_LEAD = 0.1;

export type EstimationCout = {
  bas: number; // Places + Claude Haiku, sans Dropcontact
  haut: number; // Places + Claude Sonnet + Dropcontact
};

/** Estime le coût d'un run pour un volume cible donné (fourchette basse/haute). */
export function estimerCoutRun(volumeCible: number): EstimationCout {
  const v = Number.isFinite(volumeCible) && volumeCible > 0 ? volumeCible : 0;
  const bas = v * (COUT_PLACES_PAR_LEAD + COUT_CLAUDE_HAIKU_PAR_LEAD);
  const haut =
    v *
    (COUT_PLACES_PAR_LEAD +
      COUT_CLAUDE_SONNET_PAR_LEAD +
      COUT_DROPCONTACT_PAR_LEAD);
  return { bas, haut };
}

/** Formate un montant € avec 0 ou 2 décimales selon l'ordre de grandeur. */
export function formatEur(montant: number): string {
  if (!Number.isFinite(montant)) return "—";
  const decimales = montant >= 10 ? 0 : montant >= 1 ? 1 : 2;
  return `${montant.toFixed(decimales)} €`;
}
