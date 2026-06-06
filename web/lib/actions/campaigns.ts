"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import type { CampaignStatus } from "@/lib/database.types";
import { sendLead } from "@/lib/actions/leads";

/**
 * Crée une campagne (brouillon par défaut), éventuellement liée à une verticale
 * et affectée à un client (donneur d'ordre dont les mails seront signés au nom).
 */
export async function createCampaign(
  nom: string,
  verticaleId?: string | null,
  clientNom?: string | null,
) {
  const t = nom.trim();
  if (!t) return { error: "Nom de campagne requis." };
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  const { data, error } = await supabase
    .from("campaigns")
    .insert({
      nom: t,
      verticale_id: verticaleId ?? null,
      client_nom: clientNom?.trim() || null,
      created_by: user?.id ?? null,
    })
    .select("id")
    .single();
  if (error) return { error: error.message };
  revalidatePath("/campagnes");
  return { ok: true, id: data.id as string };
}

/** Affecte (ou retire) le client d'une campagne. Vide = retire l'affectation. */
export async function setCampaignClient(id: string, clientNom: string) {
  const supabase = await createClient();
  const { error } = await supabase
    .from("campaigns")
    .update({ client_nom: clientNom.trim() || null, updated_at: new Date().toISOString() })
    .eq("id", id);
  if (error) return { error: error.message };
  revalidatePath("/campagnes");
  return { ok: true };
}

/** Change le statut d'une campagne (active / pause / terminée). */
export async function setCampaignStatus(id: string, statut: CampaignStatus) {
  const supabase = await createClient();
  const { error } = await supabase
    .from("campaigns")
    .update({ statut, updated_at: new Date().toISOString() })
    .eq("id", id);
  if (error) return { error: error.message };
  revalidatePath("/campagnes");
  return { ok: true };
}

/** Rattache des leads à une campagne (action de masse depuis l'inbox). */
export async function addLeadsToCampaign(campaignId: string, leadIds: string[]) {
  if (!leadIds.length) return { error: "Aucun lead sélectionné." };
  const supabase = await createClient();
  const { error } = await supabase
    .from("leads")
    .update({ campaign_id: campaignId })
    .in("id", leadIds);
  if (error) return { error: error.message };
  revalidatePath("/campagnes");
  revalidatePath("/inbox");
  return { ok: true, count: leadIds.length };
}

/**
 * Lance une campagne : passe la campagne « active » et envoie tous les leads
 * rattachés qui sont prêts (statut « valide »). L'envoi réel passe par Instantly
 * si la clé est configurée, sinon simulation (cf. sendLead).
 */
export async function launchCampaign(campaignId: string) {
  const supabase = await createClient();
  const { data: leads, error } = await supabase
    .from("leads")
    .select("id")
    .eq("campaign_id", campaignId)
    .eq("statut", "valide");
  if (error) return { error: error.message };

  let envoyes = 0;
  let simulation = false;
  for (const lead of leads ?? []) {
    const res = await sendLead(lead.id as string);
    if ("ok" in res && res.ok) {
      envoyes += 1;
      simulation = res.simulation ?? simulation;
    }
  }

  await supabase
    .from("campaigns")
    .update({ statut: "active", updated_at: new Date().toISOString() })
    .eq("id", campaignId);

  revalidatePath("/campagnes");
  revalidatePath("/suivi");
  revalidatePath("/inbox");
  return { ok: true, envoyes, simulation };
}
