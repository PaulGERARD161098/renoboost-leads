import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { ingestIrve, ingestRossini } from "@/lib/bornes-ingest";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
// Job lourd (fichier consolidé IRVE) : on autorise jusqu'à 5 min (plan Pro).
export const maxDuration = 300;

// Ingestion des bornes de recharge VE. Appelée par le cron Vercel (Bearer
// CRON_SECRET) ou manuellement avec ?secret=. ?source=irve|rossini|all (défaut all).
async function handle(req: NextRequest) {
  const auth = req.headers.get("authorization");
  const querySecret = req.nextUrl.searchParams.get("secret");
  const cronSecret = process.env.CRON_SECRET;
  const altSecret = process.env.AGENT_CRON_SECRET;
  const ok =
    (cronSecret && (auth === `Bearer ${cronSecret}` || querySecret === cronSecret)) ||
    (altSecret && querySecret === altSecret);
  if (!ok) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const admin = createAdminClient();
  if (!admin)
    return NextResponse.json({ error: "service role manquante" }, { status: 500 });

  const source = (req.nextUrl.searchParams.get("source") || "all").toLowerCase();
  const out: Record<string, unknown> = {};
  try {
    if (source === "irve" || source === "all") out.irve = await ingestIrve(admin);
  } catch (e) {
    out.irve = { error: String(e) };
  }
  try {
    if (source === "rossini" || source === "all") out.rossini = await ingestRossini(admin);
  } catch (e) {
    out.rossini = { error: String(e) };
  }
  return NextResponse.json({ ok: true, ...out });
}

export async function GET(req: NextRequest) {
  return handle(req);
}
export async function POST(req: NextRequest) {
  return handle(req);
}
