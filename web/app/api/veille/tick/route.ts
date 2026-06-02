import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { runVeille } from "@/lib/veille";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

async function handle(req: NextRequest) {
  const auth = req.headers.get("authorization");
  const querySecret = req.nextUrl.searchParams.get("secret");
  const cronSecret = process.env.CRON_SECRET;
  const agentSecret = process.env.AGENT_CRON_SECRET;
  const ok =
    (cronSecret && auth === `Bearer ${cronSecret}`) ||
    (agentSecret && querySecret === agentSecret);
  if (!ok) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const admin = createAdminClient();
  if (!admin)
    return NextResponse.json({ error: "service role manquante" }, { status: 500 });

  const res = await runVeille(admin);
  if ("ok" in res && res.inserted > 0) {
    await admin.from("agent_journal").insert({
      type: "info",
      message: `Veille : ${res.inserted} nouveau(x) signal(aux) détecté(s).`,
    });
  }
  return NextResponse.json(res);
}

export async function GET(req: NextRequest) {
  return handle(req);
}
export async function POST(req: NextRequest) {
  return handle(req);
}
