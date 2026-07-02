import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { deposerMessageVocal, twilioConfigure } from "@/lib/twilio";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Dépose (ou planifie) un message vocal cold-call inversé pour un lead.
// STUB télécom : on enregistre l'intention et on trace le pipe ; l'envoi réel
// via Twilio est branché plus tard (cf. lib/twilio).
export async function POST(req: NextRequest) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Non authentifié." }, { status: 401 });

  const body = await req.json().catch(() => null);
  const leadId = body?.leadId;
  const script = typeof body?.script === "string" ? body.script.trim() : null;
  if (typeof leadId !== "string")
    return NextResponse.json({ error: "leadId manquant." }, { status: 400 });

  const { data: lead } = await supabase
    .from("leads")
    .select("id, contact_tel, campaign_id")
    .eq("id", leadId)
    .single();
  if (!lead) return NextResponse.json({ error: "Lead introuvable." }, { status: 404 });
  if (!lead.contact_tel)
    return NextResponse.json({ error: "Aucun numéro de téléphone sur ce lead." }, { status: 400 });

  // Tentative de dépôt réel (no-op tant que Twilio n'est pas configuré).
  const depot = await deposerMessageVocal(supabase, {
    leadId,
    toNumber: lead.contact_tel as string,
    script: script ?? undefined,
  });
  const statut = "ok" in depot ? "depose" : "planifie";
  const twilioSid = "ok" in depot ? depot.twilioSid : null;

  const { data: vm, error } = await supabase
    .from("voicemails")
    .insert({
      lead_id: leadId,
      campaign_id: lead.campaign_id,
      to_number: lead.contact_tel,
      from_number: process.env.TWILIO_FROM_NUMBER ?? null,
      script,
      statut,
      twilio_sid: twilioSid,
      deposed_at: statut === "depose" ? new Date().toISOString() : null,
      created_by: user.id,
    })
    .select("*")
    .single();
  if (error) {
    console.error("Voicemail : insertion échouée", error.message);
    return NextResponse.json({ error: "traitement échoué" }, { status: 500 });
  }

  await supabase.from("leads").update({ call_statut: "message_depose" }).eq("id", leadId);
  await supabase.from("lead_events").insert({
    lead_id: leadId,
    type: "message_vocal_depose",
    payload: { statut, configured: twilioConfigure() },
    actor: user.id,
  });

  return NextResponse.json({ ok: true, voicemail: vm, configured: twilioConfigure() });
}
