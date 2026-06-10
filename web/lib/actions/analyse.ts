"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { potentielsDepuisAnalyse, type AnalyseResult } from "@/lib/analyse";
import { compterBornes, type ComptageBornes } from "@/lib/potentiel";

/**
 * Retient une entreprise identifiée par l'analyse d'image : crée un lead
 * « à valider » pré-scoré (terrain → potentiels v2) avec l'accroche en
 * brouillon, ou renvoie la fiche existante (doublon / déjà retenu).
 */
export async function retenirEntreprise(analyseId: string, index: number) {
  const supabase = await createClient();
  const { data: ana } = await supabase
    .from("image_analyses")
    .select("id, address, lat, lng, result, leads")
    .eq("id", analyseId)
    .maybeSingle();
  if (!ana) return { error: "Analyse introuvable." };

  const row = ana as {
    id: string;
    address: string | null;
    lat: number | null;
    lng: number | null;
    result: Record<string, unknown> | null;
    leads: Record<string, string> | null;
  };
  const result = (row.result ?? {}) as Partial<AnalyseResult>;
  const ent = result.entreprises?.[index];
  if (!ent?.nom) return { error: "Entreprise introuvable dans l'analyse." };

  const lies = row.leads ?? {};
  const dejaId = lies[String(index)];
  if (dejaId) return { ok: true, leadId: dejaId, deja: true };

  async function lier(leadId: string) {
    await supabase
      .from("image_analyses")
      .update({ leads: { ...lies, [String(index)]: leadId } })
      .eq("id", analyseId);
  }

  // Dédoublonnage pipeline : même nom d'entreprise → on pointe la fiche
  // existante au lieu de créer un doublon.
  const { data: doublon } = await supabase
    .from("leads")
    .select("id")
    .ilike("entreprise", ent.nom)
    .limit(1)
    .maybeSingle();
  if (doublon) {
    await lier(doublon.id);
    revalidatePath("/analyse");
    return { ok: true, leadId: doublon.id, deja: true };
  }

  const vide: ComptageBornes = { sur_site: 0, voisinage_1km: 0, rayon_10km: 0, types: [] };
  const bornes =
    row.lat != null && row.lng != null ? await compterBornes(row.lat, row.lng) : vide;
  const pots = potentielsDepuisAnalyse(result.terrain, bornes);

  const oppo = result.opportunites?.[0];
  const raison = [
    "Analyse image Magellan",
    ent.secteur || null,
    oppo ? `${oppo.angle} — ${oppo.pourquoi}` : result.resume || null,
  ]
    .filter(Boolean)
    .join(" · ");

  const { data: lead, error } = await supabase
    .from("leads")
    .insert({
      entreprise: ent.nom,
      adresse: row.address ?? null,
      latitude: row.lat,
      longitude: row.lng,
      score_raison: raison,
      statut: "a_valider",
      vision_satellite: pots,
      mail_sujet: result.accroche?.sujet ?? null,
      mail_corps: result.accroche?.corps ?? null,
    })
    .select("id")
    .single();
  if (error) return { error: error.message };

  await lier(lead.id);
  revalidatePath("/analyse");
  revalidatePath("/inbox");
  return { ok: true, leadId: lead.id, deja: false };
}
