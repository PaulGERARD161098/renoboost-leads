import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Webhook « rappel entrant » (cold-call inversé) : le prospect rappelle notre
// numéro dédié → on retrouve le lead par son numéro et on trace le rappel.
// STUB : prêt à recevoir le payload Twilio (voice webhook). Auth par secret.
export async function POST(req: NextRequest) {
  const secret = process.env.TWILIO_WEBHOOK_SECRET;
  const provided =
    req.headers.get("x-webhook-secret") ?? req.nextUrl.searchParams.get("secret");
  if (!secret || provided !== secret)
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const admin = createAdminClient();
  if (!admin)
    return NextResponse.json({ error: "not configured" }, { status: 500 });

  // Twilio envoie typiquement application/x-www-form-urlencoded (From, To, CallSid).
  let from: string | null = null;
  let callSid: string | null = null;
  const ct = req.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) {
    const b = (await req.json().catch(() => ({}))) as Record<string, unknown>;
    from = (b.From as string) ?? (b.from as string) ?? null;
    callSid = (b.CallSid as string) ?? null;
  } else {
    const form = await req.formData().catch(() => null);
    from = (form?.get("From") as string) ?? null;
    callSid = (form?.get("CallSid") as string) ?? null;
  }
  if (!from) return NextResponse.json({ error: "no caller" }, { status: 400 });

  // Retrouve le lead par numéro (rapprochement simple sur les derniers chiffres).
  const tail = from.replace(/\D/g, "").slice(-9);
  const { data: lead } = await admin
    .from("leads")
    .select("id")
    .ilike("contact_tel", `%${tail}%`)
    .limit(1)
    .maybeSingle();
  if (!lead) return NextResponse.json({ ok: true, matched: false });

  const now = new Date().toISOString();
  // Marque le dernier message vocal de ce lead comme « rappel reçu ».
  const { data: vm } = await admin
    .from("voicemails")
    .select("id")
    .eq("lead_id", lead.id)
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (vm)
    await admin
      .from("voicemails")
      .update({ statut: "rappel_recu", callback_at: now, twilio_sid: callSid })
      .eq("id", vm.id);

  await admin.from("leads").update({ call_statut: "rappel_recu" }).eq("id", lead.id);
  await admin.from("lead_events").insert({
    lead_id: lead.id,
    type: "rappel_recu",
    payload: { source: "twilio", call_sid: callSid },
  });

  return NextResponse.json({ ok: true, matched: true });
}
