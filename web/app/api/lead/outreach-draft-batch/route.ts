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
import { ANGLE_LABEL, type AngleReco } from "@/lib/stats-angles";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Plafond dur : garde-fou budget Anthropic (1 appel/lead). L'utilisateur
// sélectionne explicitement les leads ; on borne quand même le lot.
const MAX_LOT = 12;

// Génération EN LOT des brouillons d'approche (door d). Pré-rédige et PERSISTE
// mail_sujet/mail_corps pour les leads sélectionnés, SANS changer le statut :
// l'humain relit puis envoie (charte : propose → valide). Séquentiel pour
// rester sous les limites de débit de l'API.
export async function POST(req: NextRequest) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Non authentifié." }, { status: 401 });
  }

  const body = await req.json().catch(() => null);
  const rawIds: unknown = body?.leadIds;
  const mode: OutreachMode = body?.mode === "relance" ? "relance" : "approche";
  const leadIds = Array.isArray(rawIds)
    ? [...new Set(rawIds.filter((x): x is string => typeof x === "string"))]
    : [];
  if (leadIds.length === 0) {
    return NextResponse.json({ error: "Aucun lead sélectionné." }, { status: 400 });
  }
  if (leadIds.length > MAX_LOT) {
    return NextResponse.json(
      { error: `Lot trop grand (max ${MAX_LOT} à la fois pour maîtriser le budget).` },
      { status: 400 },
    );
  }

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { error: "Assistant non activé (clé ANTHROPIC_API_KEY absente)." },
      { status: 503 },
    );
  }

  const { data: leadsData } = await supabase
    .from("leads")
    .select(
      "id, entreprise, ville, effectif, contact_nom, libelle_naf, naf, score_raison, vision_satellite, latitude, longitude, verticale_id, verticale:verticales(nom), campaign:campaigns(client_nom)",
    )
    .in("id", leadIds);
  type Row = {
    id: string;
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
  const leads = (leadsData as Row[] | null) ?? [];
  if (leads.length === 0) {
    return NextResponse.json({ error: "Leads introuvables." }, { status: 404 });
  }

  const { data: ctx } = await supabase
    .from("app_context")
    .select("calendly_url, telephone")
    .eq("id", "main")
    .maybeSingle();
  const appCtx = ctx as { calendly_url: string | null; telephone: string | null } | null;
  const calendlyUrl = appCtx?.calendly_url ?? null;
  const telephone = appCtx?.telephone ?? null;

  // Rôles des contacts principaux (adaptent le ton), chargés en une requête.
  const { data: principauxData } = await supabase
    .from("lead_contacts")
    .select("lead_id, role")
    .eq("principal", true)
    .in("lead_id", leadIds);
  const rolePrincipal = new Map(
    ((principauxData as { lead_id: string; role: string | null }[] | null) ?? []).map(
      (c) => [c.lead_id, c.role],
    ),
  );

  // Références chantiers : chargées une fois pour tout le lot.
  const { data: refsData } = await supabase
    .from("references_chantiers")
    .select("nom, ville, lat, lng, axe, description")
    .eq("actif", true);
  const refs = (refsData as ReferenceChantier[] | null) ?? [];

  // Angle gagnant appris par cible, calculé au plus une fois par verticale.
  const recoCache = new Map<string, AngleReco | null>();
  const recoFor = async (vid: string | null): Promise<AngleReco | null> => {
    if (!vid) return null;
    if (!recoCache.has(vid)) recoCache.set(vid, await recoAngleCible(supabase, vid));
    return recoCache.get(vid) ?? null;
  };

  let done = 0;
  let failed = 0;
  for (const ld of leads) {
    const offre = Array.isArray(ld.verticale)
      ? ld.verticale[0]?.nom ?? null
      : ld.verticale?.nom ?? null;
    const client = Array.isArray(ld.campaign)
      ? ld.campaign[0]?.client_nom ?? null
      : ld.campaign?.client_nom ?? null;
    const angle = angleOutreach(ld.vision_satellite);
    // Terrain muet → angle appris sur la cible (le terrain prime quand il parle).
    const reco = angle.pilote ? null : await recoFor(ld.verticale_id);
    const angleApplique = reco
      ? { cle: reco.angle, label: ANGLE_LABEL[reco.angle] }
      : null;
    const axe = angle.pilote ? angle.cle : angleApplique?.cle ?? null;
    const axeSource = angle.pilote ? "terrain" : angleApplique ? "appris" : null;
    const reference = choisirReference(refs, ld, axe);
    const draft = await generateOutreachDraft(
      apiKey,
      mode,
      {
        entreprise: ld.entreprise,
        ville: ld.ville,
        secteur: ld.libelle_naf ?? ld.naf,
        effectif: ld.effectif,
        contact_nom: ld.contact_nom,
        contact_role: rolePrincipal.get(ld.id) ?? null,
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
      failed++;
      continue;
    }
    const { error: upErr } = await supabase
      .from("leads")
      .update({
        mail_sujet: draft.sujet,
        mail_corps: draft.corps,
        mail_angle: axe,
        mail_angle_source: axeSource,
      })
      .eq("id", ld.id);
    if (upErr) {
      failed++;
      continue;
    }
    await supabase.from("lead_events").insert({
      lead_id: ld.id,
      type: "note",
      payload: { action: "brouillon_approche_prefait", mode },
      actor: user.id,
    });
    done++;
  }

  return NextResponse.json({ done, failed, total: leads.length });
}
