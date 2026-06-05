"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import type { LeadStatus } from "@/lib/database.types";

async function logEvent(
  leadId: string,
  type: string,
  payload: Record<string, unknown> = {},
) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  await supabase.from("lead_events").insert({
    lead_id: leadId,
    type,
    payload,
    actor: user?.id ?? null,
  });
}

export async function updateLeadEmail(
  leadId: string,
  sujet: string,
  corps: string,
) {
  const supabase = await createClient();
  const { error } = await supabase
    .from("leads")
    .update({ mail_sujet: sujet, mail_corps: corps, statut: "valide" })
    .eq("id", leadId);
  if (error) return { error: error.message };
  await logEvent(leadId, "note", { action: "edition_mail" });
  revalidatePath(`/leads/${leadId}`);
  return { ok: true };
}

/**
 * Applique un brouillon de réponse suggéré par Magellan : l'écrit dans le
 * brouillon sortant du lead (mail_sujet/mail_corps) SANS toucher au statut
 * (le lead reste « répondu »), et marque la suggestion comme suivie (mesure
 * de la valeur). Jamais d'envoi — propose → valide.
 */
export async function appliquerBrouillonReponse(
  leadId: string,
  suggestionId: string,
  sujet: string,
  corps: string,
) {
  const supabase = await createClient();
  const { error } = await supabase
    .from("leads")
    .update({ mail_sujet: sujet || null, mail_corps: corps })
    .eq("id", leadId);
  if (error) return { error: error.message };
  await supabase
    .from("lead_reply_suggestions")
    .update({ used: true })
    .eq("id", suggestionId);
  await logEvent(leadId, "note", { action: "brouillon_reponse_applique" });
  revalidatePath(`/leads/${leadId}`);
  return { ok: true };
}

export async function setLeadStatus(leadId: string, statut: LeadStatus) {
  const supabase = await createClient();
  const { error } = await supabase
    .from("leads")
    .update({ statut })
    .eq("id", leadId);
  if (error) return { error: error.message };
  if (statut === "ecarte") await logEvent(leadId, "ecarte");
  revalidatePath(`/leads/${leadId}`);
  revalidatePath("/inbox");
  revalidatePath("/suivi");
  return { ok: true };
}

/** Planifie (ou efface) la date de prochaine relance d'un lead. */
export async function planifierRelance(leadId: string, dateISO: string | null) {
  const supabase = await createClient();
  const { error } = await supabase
    .from("leads")
    .update({ relance_at: dateISO })
    .eq("id", leadId);
  if (error) return { error: error.message };
  await logEvent(leadId, "note", { action: "relance_planifiee", date: dateISO });
  revalidatePath(`/leads/${leadId}`);
  revalidatePath("/inbox");
  revalidatePath("/suivi");
  return { ok: true };
}

/** Ajoute une note libre à un lead (consignée dans l'historique). */
export async function addLeadNote(leadId: string, texte: string) {
  const t = texte.trim();
  if (!t) return { error: "Note vide" };
  await logEvent(leadId, "note", { texte: t });
  revalidatePath(`/leads/${leadId}`);
  return { ok: true };
}

/**
 * Marque un RDV pris (incrément B) : statut rdv_pris + sortie des files de
 * relance (relance_at) et d'appel (call_statut). Tracé. Appelé manuellement
 * (fiche) ou par le webhook Calendly.
 */
export async function marquerRdvPris(leadId: string) {
  const supabase = await createClient();
  const { error } = await supabase
    .from("leads")
    .update({ statut: "rdv_pris", relance_at: null, call_statut: null })
    .eq("id", leadId);
  if (error) return { error: error.message };
  await logEvent(leadId, "note", { action: "rdv_pris" });
  revalidatePath("/suivi");
  revalidatePath("/inbox");
  revalidatePath(`/leads/${leadId}`);
  return { ok: true };
}

/** Marque un lead « à relancer » et trace l'événement de relance. */
export async function relancerLead(leadId: string) {
  const supabase = await createClient();
  const { error } = await supabase
    .from("leads")
    .update({ statut: "a_relancer" })
    .eq("id", leadId);
  if (error) return { error: error.message };
  await logEvent(leadId, "relance");
  revalidatePath("/suivi");
  revalidatePath("/inbox");
  revalidatePath(`/leads/${leadId}`);
  return { ok: true };
}

/** Mise à jour groupée du statut de plusieurs leads (actions de masse). */
export async function setLeadsStatus(ids: string[], statut: LeadStatus) {
  if (!ids.length) return { error: "Aucun lead sélectionné" };
  const supabase = await createClient();
  const { error } = await supabase
    .from("leads")
    .update({ statut })
    .in("id", ids);
  if (error) return { error: error.message };
  revalidatePath("/inbox");
  revalidatePath("/suivi");
  return { ok: true, count: ids.length };
}

/**
 * Envoi via Instantly. Sans clé API configurée → mode simulation
 * (le lead passe « envoyé » mais aucun email réel n'est transmis).
 */
export async function sendLead(leadId: string) {
  const supabase = await createClient();
  const { data: lead, error: readErr } = await supabase
    .from("leads")
    .select("*")
    .eq("id", leadId)
    .single();
  if (readErr || !lead) return { error: readErr?.message ?? "Lead introuvable" };
  if (!lead.contact_email) return { error: "Aucun email de contact" };

  const simulation = !process.env.INSTANTLY_API_KEY;
  // TODO(M2): appel réel API Instantly quand la clé est fournie.

  const { error } = await supabase
    .from("leads")
    // relance_at remis à zéro : l'envoi réamorce l'horloge de relance auto.
    .update({ statut: "envoye", sent_at: new Date().toISOString(), relance_at: null })
    .eq("id", leadId);
  if (error) return { error: error.message };
  await logEvent(leadId, "envoye", { simulation });
  // Trace le mail sortant dans le fil de conversation.
  await supabase.from("lead_messages").insert({
    lead_id: leadId,
    direction: "out",
    sujet: lead.mail_sujet,
    corps: lead.mail_corps,
    to_email: lead.contact_email,
    source: simulation ? "systeme" : "instantly",
  });
  revalidatePath(`/leads/${leadId}`);
  revalidatePath("/inbox");
  revalidatePath("/suivi");
  return { ok: true, simulation };
}

/** Droit à l'effacement (RGPD) : anonymise les données personnelles du lead. */
export async function forgetLead(leadId: string) {
  const supabase = await createClient();
  const { error } = await supabase
    .from("leads")
    .update({
      contact_nom: null,
      contact_email: null,
      contact_tel: null,
      mail_corps: null,
      statut: "ecarte",
    })
    .eq("id", leadId);
  if (error) return { error: error.message };
  await logEvent(leadId, "oubli_rgpd");
  revalidatePath(`/leads/${leadId}`);
  revalidatePath("/inbox");
  return { ok: true };
}
