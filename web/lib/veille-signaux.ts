// Helpers autour des signaux de veille rattachés à un lead — partagés par
// l'analyse satellite (boost du potentiel bornes) et la fiche lead (affichage).
// Module léger : pas d'appel IA, juste de la lecture Supabase + un prédicat.

import type { SupabaseClient } from "@supabase/supabase-js";
import type { VeilleSignal } from "@/lib/database.types";
import { signalTypesPourIntentions } from "@/lib/intentions";

// Types de signaux qui traduisent une électrification (flotte VE / IRVE) : ce
// sont eux qui rendent un site plus mûr pour des bornes de recharge.
export const TYPES_SIGNAL_VE = ["ve_flotte", "irve", "electrification"] as const;

/** Un signal traduit-il une dynamique VE (→ pertinent pour le potentiel bornes) ? */
export function estSignalVE(s: Pick<VeilleSignal, "type">): boolean {
  return s.type != null && (TYPES_SIGNAL_VE as readonly string[]).includes(s.type);
}

/** Signaux de veille rattachés à un lead, les plus chauds d'abord. */
export async function signauxDuLead(
  supabase: SupabaseClient,
  leadId: string,
): Promise<VeilleSignal[]> {
  const { data } = await supabase
    .from("veille_signaux")
    .select("*")
    .eq("lead_id", leadId)
    .order("score_intention", { ascending: false, nullsFirst: false });
  return (data as VeilleSignal[] | null) ?? [];
}

/**
 * Signaux de veille « réels » correspondant aux intentions d'une Cible — les
 * boîtes qui prouvent l'intention sur le terrain (vs le proxy NAF). Filtre par
 * type de signal mappé, exclut les signaux écartés, les plus chauds d'abord.
 * Renvoie `[]` si la cible n'a pas d'intention à signal direct (ex. fiscal seul).
 */
export async function signauxPourIntentions(
  supabase: SupabaseClient,
  intentions: string[],
  limit = 8,
): Promise<VeilleSignal[]> {
  const types = signalTypesPourIntentions(intentions);
  if (types.length === 0) return [];
  const { data } = await supabase
    .from("veille_signaux")
    .select("*")
    .in("type", types)
    .neq("statut", "ecarte")
    .order("score_intention", { ascending: false, nullsFirst: false })
    .limit(limit);
  return (data as VeilleSignal[] | null) ?? [];
}
