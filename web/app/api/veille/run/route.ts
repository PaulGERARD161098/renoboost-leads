import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { runVeille } from "@/lib/veille";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 120;

export async function POST() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Non authentifié." }, { status: 401 });

  const res = await runVeille(supabase);
  return NextResponse.json(res);
}
