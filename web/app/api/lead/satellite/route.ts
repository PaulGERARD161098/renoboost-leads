import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { analyseSatellite } from "@/lib/satellite";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

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

  const res = await analyseSatellite(supabase, leadId);
  if ("error" in res) return NextResponse.json({ error: res.error });
  return NextResponse.json({ ok: true, result: res.result });
}
