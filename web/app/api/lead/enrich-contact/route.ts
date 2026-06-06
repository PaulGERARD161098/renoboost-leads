import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { enrichContact } from "@/lib/enrich-contact";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
// Dropcontact répond par polling (POST puis GET) : on laisse du temps à la
// fonction. Souvent <30 s pour 1 lead ; on borne à 60 s côté lib comme route.
export const maxDuration = 60;

export async function POST(req: NextRequest) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Non authentifié." }, { status: 401 });

  const body = await req.json().catch(() => null);
  const leadId = body?.leadId;
  if (typeof leadId !== "string")
    return NextResponse.json({ error: "leadId manquant." }, { status: 400 });

  const res = await enrichContact(supabase, leadId);
  if ("error" in res)
    return NextResponse.json({ error: res.error, action: res.action, retry: res.retry });

  await supabase.from("lead_events").insert({
    lead_id: leadId,
    type: "note",
    payload: { action: "enrichissement_contact", trouve: res.trouve },
    actor: user.id,
  });
  return NextResponse.json({ ok: true, result: res.result, trouve: res.trouve });
}
