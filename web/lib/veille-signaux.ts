// Helpers autour des signaux de veille rattachés à un lead — partagés par
// l'analyse satellite (boost du potentiel bornes) et la fiche lead (affichage).
// Module léger : pas d'appel IA, juste de la lecture Supabase + un prédicat.

import type { SupabaseClient } from "@supabase/supabase-js";
import type { VeilleSignal } from "@/lib/database.types";

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
