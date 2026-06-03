import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { ingestIrve } from "@/lib/bornes-ingest";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
// Job lourd (fichier consolidé IRVE) : jusqu'à 5 min (plan Pro).
export const maxDuration = 300;

// Ingestion des bornes IRVE (open-data). Déclenchée par le cron Vercel
// (Bearer CRON_SECRET / ?secret=) OU par un utilisateur connecté (bouton in-app).
async function handle(req: NextRequest) {
  const auth = req.headers.get("authorization");
  const querySecret = req.nextUrl.searchParams.get("secret");
  const cronSecret = process.env.CRON_SECRET;
  const altSecret = process.env.AGENT_CRON_SECRET;
  let ok =
    Boolean(cronSecret && (auth === `Bearer ${cronSecret}` || querySecret === cronSecret)) ||
    Boolean(altSecret && querySecret === altSecret);
  if (!ok) {
    const sb = await createClient();
    const {
      data: { user },
    } = await sb.auth.getUser();
    ok = Boolean(user);
  }
  if (!ok) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const admin = createAdminClient();
  if (!admin)
    return NextResponse.json({ error: "service role manquante" }, { status: 500 });

  let result: Record<string, unknown>;
  try {
    result = await ingestIrve(admin);
  } catch (e) {
    result = { error: String(e) };
  }
  // Trace en base (observabilité sans logs Vercel).
  try {
    await admin.from("agent_journal").insert({
      type: "bornes_ingest",
      message: "Ingestion bornes IRVE",
      payload: result,
    });
  } catch {
    /* le log ne doit jamais casser l'ingestion */
  }
  return NextResponse.json({ ok: true, ...result });
}

export async function GET(req: NextRequest) {
  return handle(req);
}
export async function POST(req: NextRequest) {
  return handle(req);
}
