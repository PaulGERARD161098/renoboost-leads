import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { generateOutreachDraft, type OutreachMode } from "@/lib/outreach";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Non authentifié." }, { status: 401 });
  }

  const body = await req.json().catch(() => null);
  const leadId: string | undefined = body?.leadId;
  const mode: OutreachMode = body?.mode === "relance" ? "relance" : "approche";
  if (!leadId) {
    return NextResponse.json({ error: "leadId manquant." }, { status: 400 });
  }

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { error: "Assistant non activé (clé ANTHROPIC_API_KEY absente)." },
      { status: 503 },
    );
  }

  const { data: lead } = await supabase
    .from("leads")
    .select(
      "entreprise, ville, effectif, contact_nom, libelle_naf, naf, score_raison, vision_satellite, verticale:verticales(nom), campaign:campaigns(client_nom)",
    )
    .eq("id", leadId)
    .maybeSingle();
  if (!lead) {
    return NextResponse.json({ error: "Lead introuvable." }, { status: 404 });
  }
  const ld = lead as {
    entreprise: string;
    ville: string | null;
    effectif: string | null;
    contact_nom: string | null;
    libelle_naf: string | null;
    naf: string | null;
    score_raison: string | null;
    vision_satellite: Record<string, unknown> | null;
    verticale?: { nom?: string } | { nom?: string }[];
    campaign?: { client_nom?: string | null } | { client_nom?: string | null }[];
  };
  const offre = Array.isArray(ld.verticale)
    ? ld.verticale[0]?.nom ?? null
    : ld.verticale?.nom ?? null;
  const client = Array.isArray(ld.campaign)
    ? ld.campaign[0]?.client_nom ?? null
    : ld.campaign?.client_nom ?? null;

  const { data: ctx } = await supabase
    .from("app_context")
    .select("calendly_url")
    .eq("id", "main")
    .maybeSingle();
  const calendlyUrl = (ctx as { calendly_url: string | null } | null)?.calendly_url ?? null;

  const draft = await generateOutreachDraft(
    apiKey,
    mode,
    {
      entreprise: ld.entreprise,
      ville: ld.ville,
      secteur: ld.libelle_naf ?? ld.naf,
      effectif: ld.effectif,
      contact_nom: ld.contact_nom,
      score_raison: ld.score_raison,
      vision: ld.vision_satellite,
    },
    offre,
    calendlyUrl,
    client,
  );
  if (!draft.ok) {
    return NextResponse.json({ error: draft.error }, { status: draft.status });
  }
  return NextResponse.json({ sujet: draft.sujet, corps: draft.corps });
}
