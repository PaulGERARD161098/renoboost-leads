import { NextRequest, NextResponse } from "next/server";
import { createHmac, timingSafeEqual } from "crypto";
import { createAdminClient } from "@/lib/supabase/admin";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Webhook Calendly (incrément B) : un prospect réserve un créneau → on bascule
// le lead correspondant en `rdv_pris` et on le sort des files de relance/appel.
// Capture entrante uniquement (aucune action sortante).
//
// Auth, par ordre de préférence :
//   1. CALENDLY_WEBHOOK_SIGNING_KEY → vérif HMAC officielle (header
//      `Calendly-Webhook-Signature: t=...,v1=...`, signature = HMAC-SHA256 sur `t.body`).
//   2. CALENDLY_WEBHOOK_SECRET → secret partagé via `?secret=` ou header.
//   3. sinon → 401 (non configuré).

function safeEqual(a: string, b: string): boolean {
  const ba = Buffer.from(a);
  const bb = Buffer.from(b);
  return ba.length === bb.length && timingSafeEqual(ba, bb);
}

function verifySignature(signingKey: string, header: string | null, raw: string): boolean {
  if (!header) return false;
  const parts = Object.fromEntries(
    header.split(",").map((kv) => {
      const [k, v] = kv.split("=");
      return [k?.trim(), v?.trim()];
    }),
  );
  const t = parts["t"];
  const v1 = parts["v1"];
  if (!t || !v1) return false;
  const expected = createHmac("sha256", signingKey).update(`${t}.${raw}`).digest("hex");
  return safeEqual(expected, v1);
}

export async function POST(req: NextRequest) {
  const raw = await req.text();

  const signingKey = process.env.CALENDLY_WEBHOOK_SIGNING_KEY;
  const sharedSecret = process.env.CALENDLY_WEBHOOK_SECRET;
  let authed = false;
  if (signingKey) {
    authed = verifySignature(
      signingKey,
      req.headers.get("calendly-webhook-signature"),
      raw,
    );
  } else if (sharedSecret) {
    const provided =
      req.headers.get("x-webhook-secret") ?? req.nextUrl.searchParams.get("secret");
    authed = provided === sharedSecret;
  }
  if (!authed) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const admin = createAdminClient();
  if (!admin) {
    console.error("Webhook Calendly : SUPABASE_SERVICE_ROLE_KEY manquante.");
    return NextResponse.json({ error: "not configured" }, { status: 500 });
  }

  const body = (() => {
    try {
      return JSON.parse(raw) as Record<string, unknown>;
    } catch {
      return null;
    }
  })();
  if (!body) return NextResponse.json({ error: "bad payload" }, { status: 400 });

  // On ne traite que la création de RDV.
  const event = String(body.event ?? "");
  if (event !== "invitee.created") {
    return NextResponse.json({ ok: true, ignored: event || "no_event" });
  }

  const payload = (body.payload ?? {}) as Record<string, unknown>;
  const email =
    typeof payload.email === "string" && payload.email.trim()
      ? payload.email.trim()
      : null;
  if (!email) return NextResponse.json({ error: "no invitee email" }, { status: 400 });

  // Retrouve le lead par email de contact ; on ne touche pas un lead déjà écarté.
  const { data: found, error: findErr } = await admin
    .from("leads")
    .select("id, statut")
    .ilike("contact_email", email)
    .neq("statut", "ecarte")
    .limit(1)
    .maybeSingle();
  if (findErr) {
    console.error("Webhook Calendly : lookup", findErr.message);
    return NextResponse.json({ error: "lookup failed" }, { status: 500 });
  }
  if (!found) return NextResponse.json({ ok: true, matched: false });

  const { error: updErr } = await admin
    .from("leads")
    .update({ statut: "rdv_pris", relance_at: null, call_statut: null })
    .eq("id", found.id);
  if (updErr) {
    console.error("Webhook Calendly : update", updErr.message);
    return NextResponse.json({ error: "update failed" }, { status: 500 });
  }

  await admin.from("lead_events").insert({
    lead_id: found.id,
    type: "note",
    payload: { action: "rdv_pris", source: "calendly" },
  });

  return NextResponse.json({ ok: true, matched: true });
}
