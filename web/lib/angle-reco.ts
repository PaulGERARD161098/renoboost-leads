// Reco d'angle apprise pour une cible (verticale), partagée par la fiche lead et
// la génération du brouillon (auto-application quand l'analyse terrain est muette).
import type { SupabaseClient } from "@supabase/supabase-js";
import {
  angleGagnantParCible,
  type AngleReco,
  type LeadStatCible,
} from "@/lib/stats-angles";

export async function recoAngleCible(
  supabase: SupabaseClient,
  verticaleId: string | null,
): Promise<AngleReco | null> {
  if (!verticaleId) return null;
  const { data } = await supabase
    .from("leads")
    .select("verticale_id, statut, mail_angle, sent_at, replied_at")
    .eq("verticale_id", verticaleId);
  return angleGagnantParCible((data as LeadStatCible[] | null) ?? [])[0] ?? null;
}
