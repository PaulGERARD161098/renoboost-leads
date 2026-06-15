import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import {
  angleOutreach,
  choisirReference,
  generateOutreachDraft,
  type OutreachMode,
  type ReferenceChantier,
} from "@/lib/outreach";
import { recoAngleCible } from "@/lib/angle-reco";
import { ANGLE_LABEL } from "@/lib/stats-angles";

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
      "entreprise, ville, effectif, contact_nom, libelle_naf, naf, score_raison, vision_satellite, latitude, longitude, verticale_id, verticale:verticales(nom), campaign:campaigns(client_nom)",
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
    verticale_id: string | null;
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

  // Rôle du contact principal (adapte le ton : DAF → ROI, DG → stratégie…).
  const { data: principal } = await supabase
    .from("lead_contacts")
    .select("role")
    .eq("lead_id", leadId)
    .eq("principal", true)
    .maybeSingle();
  const contactRole = (principal as { role: string | null } | null)?.role ?? null;

  // Angle terrain (analyse du site). S'il est muet, on applique l'angle gagnant
  // APPRIS sur la cible (boucle d'apprentissage refermée) — le terrain prime
  // toujours quand il parle.
  const angle = angleOutreach(ld.vision_satellite);
  const recoAppris = angle.pilote
    ? null
    : await recoAngleCible(supabase, ld.verticale_id);
  const angleApplique = recoAppris
    ? { cle: recoAppris.angle, label: ANGLE_LABEL[recoAppris.angle] }
    : null;
  const axeReference = angle.pilote ? angle.cle : angleApplique?.cle ?? null;

  // Preuve sociale : la référence chantier la plus proche, sur l'axe du mail.
  const { data: refsData } = await supabase
    .from("references_chantiers")
    .select("nom, ville, lat, lng, axe, description")
    .eq("actif", true);
  const reference = choisirReference(
    (refsData as ReferenceChantier[] | null) ?? [],
    ld,
    axeReference,
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
      contact_role: contactRole,
      score_raison: ld.score_raison,
      vision: ld.vision_satellite,
    },
    offre,
    calendlyUrl,
    client,
    telephone,
    reference,
    angleApplique,
  );
  if (!draft.ok) {
    return NextResponse.json({ error: draft.error }, { status: draft.status });
  }
  // Persiste l'axe retenu (terrain sinon appris) pour les stats + le lift par angle.
  await supabase
    .from("leads")
    .update({ mail_angle: axeReference })
    .eq("id", leadId);
  return NextResponse.json({
    sujet: draft.sujet,
    corps: draft.corps,
    angle,
    angleApplique,
  });
}
