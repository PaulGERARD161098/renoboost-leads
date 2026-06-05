import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import {
  generateOutreachDraft,
  solaireFromVision,
  type OutreachMode,
} from "@/lib/outreach";

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
      "id, entreprise, ville, effectif, contact_nom, libelle_naf, naf, score_raison, vision_satellite, verticale:verticales(nom)",
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
    verticale?: { nom?: string } | { nom?: string }[];
  };
  const leads = (leadsData as Row[] | null) ?? [];
  if (leads.length === 0) {
    return NextResponse.json({ error: "Leads introuvables." }, { status: 404 });
  }

  const { data: ctx } = await supabase
    .from("app_context")
    .select("calendly_url")
    .eq("id", "main")
    .maybeSingle();
  const calendlyUrl = (ctx as { calendly_url: string | null } | null)?.calendly_url ?? null;

  let done = 0;
  let failed = 0;
  for (const ld of leads) {
    const offre = Array.isArray(ld.verticale)
      ? ld.verticale[0]?.nom ?? null
      : ld.verticale?.nom ?? null;
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
        solaire: solaireFromVision(ld.vision_satellite),
      },
      offre,
      calendlyUrl,
    );
    if (!draft.ok) {
      failed++;
      continue;
    }
    const { error: upErr } = await supabase
      .from("leads")
      .update({ mail_sujet: draft.sujet, mail_corps: draft.corps })
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
