import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Mappe le type d'événement Instantly (libellés variables) vers notre modèle.
function classify(
  raw: unknown,
): "envoye" | "ouvert" | "repondu" | "rebond" | null {
  const e = String(raw ?? "").toLowerCase();
  if (e.includes("bounce")) return "rebond";
  if (e.includes("reply") || e.includes("replied")) return "repondu";
  if (e.includes("open")) return "ouvert";
  if (e.includes("sent")) return "envoye";
  return null;
}

function pick(body: Record<string, unknown>, keys: string[]): string | null {
  for (const k of keys) {
    const v = body[k];
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  return null;
}

export async function POST(req: NextRequest) {
  // Authentification du webhook par secret partagé.
  const secret = process.env.INSTANTLY_WEBHOOK_SECRET;
  const provided =
    req.headers.get("x-webhook-secret") ??
    req.nextUrl.searchParams.get("secret");
  if (!secret || provided !== secret) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const admin = createAdminClient();
  if (!admin) {
    console.error("Webhook Instantly : SUPABASE_SERVICE_ROLE_KEY manquante.");
    return NextResponse.json({ error: "not configured" }, { status: 500 });
  }

  const body = (await req.json().catch(() => null)) as Record<
    string,
    unknown
  > | null;
  if (!body) return NextResponse.json({ error: "bad payload" }, { status: 400 });

  const kind = classify(body.event_type ?? body.event ?? body.type);
  if (!kind) return NextResponse.json({ ok: true, ignored: true });

  const email = pick(body, ["lead_email", "email", "to_email", "to"]);
  const instantlyId = pick(body, ["lead_id", "id", "instantly_id"]);
  if (!email && !instantlyId) {
    return NextResponse.json({ error: "no lead identifier" }, { status: 400 });
  }

  // Retrouve le lead par instantly_id en priorité, sinon par email.
  let query = admin.from("leads").select("id, statut").limit(1);
  query = instantlyId
    ? query.eq("instantly_id", instantlyId)
    : query.ilike("contact_email", email!);
  const { data: found, error: findErr } = await query.maybeSingle();
  if (findErr) {
    console.error("Webhook Instantly : lookup", findErr.message);
    return NextResponse.json({ error: "lookup failed" }, { status: 500 });
  }
  if (!found) return NextResponse.json({ ok: true, matched: false });

  const now = new Date().toISOString();
  const update: Record<string, unknown> = {};
  if (kind === "envoye") {
    update.sent_at = now;
    update.statut = "envoye";
  } else if (kind === "ouvert") {
    update.opened_at = now;
    update.statut = "ouvert";
  } else if (kind === "repondu") {
    update.replied_at = now;
    update.statut = "repondu";
  } else if (kind === "rebond") {
    update.bounced_at = now;
  }

  const { error: updErr } = await admin
    .from("leads")
    .update(update)
    .eq("id", found.id);
  if (updErr) {
    console.error("Webhook Instantly : update", updErr.message);
    return NextResponse.json({ error: "update failed" }, { status: 500 });
  }

  await admin
    .from("lead_events")
    .insert({ lead_id: found.id, type: kind, payload: { source: "instantly" } });

  return NextResponse.json({ ok: true, matched: true, kind });
}
