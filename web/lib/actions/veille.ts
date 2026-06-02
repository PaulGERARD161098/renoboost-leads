"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";

/** Retient un signal de veille : en fait un lead dans le pipeline + marque "converti". */
export async function retenirSignal(signalId: string) {
  const supabase = await createClient();
  const { data: sig } = await supabase
    .from("veille_signaux")
    .select("*")
    .eq("id", signalId)
    .single();
  if (!sig) return { error: "Signal introuvable" };

  const raison = [sig.declencheur, sig.angle].filter(Boolean).join(" — ") || sig.resume;
  const { data: lead, error } = await supabase
    .from("leads")
    .insert({
      entreprise: sig.entreprise,
      ville: sig.ville ?? null,
      adresse: sig.ville ?? null,
      score: sig.score_intention ?? sig.score_fit ?? null,
      score_raison: raison ? `Veille — ${raison}` : "Signal de veille",
      site_web: sig.source_url ?? null,
      statut: "a_valider",
    })
    .select("id")
    .single();
  if (error) return { error: error.message };

  await supabase
    .from("veille_signaux")
    .update({ statut: "converti", lead_id: lead.id })
    .eq("id", signalId);
  revalidatePath("/veille");
  revalidatePath("/inbox");
  return { ok: true, leadId: lead.id };
}

export async function ecarterSignal(signalId: string) {
  const supabase = await createClient();
  const { error } = await supabase
    .from("veille_signaux")
    .update({ statut: "ecarte" })
    .eq("id", signalId);
  if (error) return { error: error.message };
  revalidatePath("/veille");
  return { ok: true };
}
