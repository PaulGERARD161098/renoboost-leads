import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import {
  angleOutreach,
  choisirReference,
  generateOutreachDraft,
  type OutreachMode,
  type ReferenceChantier,
} from "@/lib/outreach";

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
      "entreprise, ville, effectif, contact_nom, libelle_naf, naf, score_raison, vision_satellite, latitude, longitude, verticale:verticales(nom), campaign:campaigns(client_nom)",
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
    latitude: number | null;
    longitude: number | null;
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
    .select("calendly_url, telephone")
    .eq("id", "main")
    .maybeSingle();
  const appCtx = ctx as { calendly_url: string | null; telephone: string | null } | null;
  const calendlyUrl = appCtx?.calendly_url ?? null;
  const telephone = appCtx?.telephone ?? null;

  // Preuve sociale : la référence chantier la plus proche, sur l'axe du mail.
  const angle = angleOutreach(ld.vision_satellite);
  const { data: refsData } = await supabase
    .from("references_chantiers")
    .select("nom, ville, lat, lng, axe, description")
    .eq("actif", true);
  const reference = choisirReference(
    (refsData as ReferenceChantier[] | null) ?? [],
    ld,
    angle.pilote ? angle.cle : null,
  );

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
    telephone,
    reference,
  );
  if (!draft.ok) {
    return NextResponse.json({ error: draft.error }, { status: draft.status });
  }
  // `angle` : dit à l'UI si le brouillon est piloté par l'analyse du site
  // (et sur quel axe) — transparence demandée par les retours terrain. L'axe
  // est aussi persisté sur le lead (mail_angle) pour les stats par angle.
  await supabase
    .from("leads")
    .update({ mail_angle: angle.pilote ? angle.cle : null })
    .eq("id", leadId);
  return NextResponse.json({
    sujet: draft.sujet,
    corps: draft.corps,
    angle,
  });
}
