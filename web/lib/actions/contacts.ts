"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";

export type ContactInput = {
  nom: string;
  role: string;
  email: string;
  tel: string;
};

export async function ajouterContact(leadId: string, input: ContactInput) {
  const nom = input.nom.trim();
  if (!nom) return { error: "Le nom est obligatoire." };
  const supabase = await createClient();

  // Premier contact du lead → principal d'office.
  const { count } = await supabase
    .from("lead_contacts")
    .select("id", { count: "exact", head: true })
    .eq("lead_id", leadId);
  const principal = (count ?? 0) === 0;

  const { data, error } = await supabase
    .from("lead_contacts")
    .insert({
      lead_id: leadId,
      nom,
      role: input.role.trim() || null,
      email: input.email.trim() || null,
      tel: input.tel.trim() || null,
      principal,
    })
    .select("id")
    .single();
  if (error) return { error: error.message };
  if (principal) await syncPrincipal(leadId, data.id);
  revalidatePath(`/leads/${leadId}`);
  return { ok: true };
}

export async function supprimerContact(leadId: string, contactId: string) {
  const supabase = await createClient();
  const { error } = await supabase.from("lead_contacts").delete().eq("id", contactId);
  if (error) return { error: error.message };
  revalidatePath(`/leads/${leadId}`);
  return { ok: true };
}

/**
 * Définit le contact principal et le recopie dans leads.contact_* — le
 * pipeline mail existant (envois, brouillons) continue de lire ces colonnes.
 */
export async function definirPrincipal(leadId: string, contactId: string) {
  const supabase = await createClient();
  await supabase.from("lead_contacts").update({ principal: false }).eq("lead_id", leadId);
  const { error } = await supabase
    .from("lead_contacts")
    .update({ principal: true })
    .eq("id", contactId);
  if (error) return { error: error.message };
  await syncPrincipal(leadId, contactId);
  revalidatePath(`/leads/${leadId}`);
  return { ok: true };
}

async function syncPrincipal(leadId: string, contactId: string) {
  const supabase = await createClient();
  const { data } = await supabase
    .from("lead_contacts")
    .select("nom, email, tel, linkedin")
    .eq("id", contactId)
    .maybeSingle();
  if (!data) return;
  const c = data as { nom: string; email: string | null; tel: string | null; linkedin: string | null };
  await supabase
    .from("leads")
    .update({
      contact_nom: c.nom,
      contact_email: c.email,
      contact_tel: c.tel,
      contact_linkedin: c.linkedin,
    })
    .eq("id", leadId);
}
