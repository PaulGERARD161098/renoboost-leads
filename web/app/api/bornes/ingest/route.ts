import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { ingestIrve, ingestRossini } from "@/lib/bornes-ingest";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
// Job lourd (fichier consolidé IRVE) : on autorise jusqu'à 5 min (plan Pro).
export const maxDuration = 300;

// Ingestion des bornes de recharge VE. Appelée par le cron Vercel (Bearer
// CRON_SECRET) ou manuellement avec ?secret=. ?source=irve|rossini|all (défaut all).
async function handle(req: NextRequest) {
  // Autorisé si : (a) cron Vercel (Bearer CRON_SECRET / ?secret=), OU
  // (b) un utilisateur connecté au CRM (déclenchement par bouton dans l'app).
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

  const source = (req.nextUrl.searchParams.get("source") || "all").toLowerCase();
  const out: Record<string, unknown> = {};
  // Rossini D'ABORD : petit et fiable, il aboutit même si IRVE (gros fichier)
  // dépasse ensuite le temps imparti.
  try {
    if (source === "rossini" || source === "all") out.rossini = await ingestRossini(admin);
  } catch (e) {
    out.rossini = { error: String(e) };
  }
  try {
    if (source === "irve" || source === "all") out.irve = await ingestIrve(admin);
  } catch (e) {
    out.irve = { error: String(e) };
  }
  // Trace le résultat en base (observabilité : lisible même sans logs Vercel).
  try {
    await admin.from("agent_journal").insert({
      type: "bornes_ingest",
      message: `Ingestion bornes (source=${source})`,
      payload: out,
    });
  } catch {
    /* le log ne doit jamais casser l'ingestion */
  }
  return NextResponse.json({ ok: true, ...out });
}

export async function GET(req: NextRequest) {
  return handle(req);
}
export async function POST(req: NextRequest) {
  return handle(req);
}
