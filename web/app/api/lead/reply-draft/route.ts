import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import type { LeadMessage, ReplyCategorie } from "@/lib/database.types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MODEL = "claude-sonnet-4-6";
const MAX_TOKENS = 900;

const CATEGORIES: ReplyCategorie[] = [
  "interesse",
  "info",
  "plus_tard",
  "mauvais_interlocuteur",
  "pas_interesse",
  "absence",
  "autre",
];

function buildPrompt(
  entreprise: string,
  verticale: string | null,
  contact: string | null,
  thread: LeadMessage[],
): string {
  const fil = thread
    .map((m) => {
      const qui = m.direction === "out" ? "NOUS" : "PROSPECT";
      const sujet = m.sujet ? `[${m.sujet}] ` : "";
      return `${qui}: ${sujet}${m.corps ?? "(vide)"}`;
    })
    .join("\n\n");

  return `Tu es l'assistant commercial de RénoBoost${
    verticale ? ` (offre : ${verticale})` : ""
  }. Un prospect B2B (${entreprise}${
    contact ? `, contact ${contact}` : ""
  }) vient de répondre à notre prospection. Analyse le fil et prépare la réponse.

FIL DE CONVERSATION (du plus ancien au plus récent) :
${fil}

Tâche :
1. CLASSE la dernière réponse du prospect dans UNE catégorie parmi :
   - "interesse" : marque de l'intérêt, veut un RDV / une démo / un devis.
   - "info" : pose une question, demande une précision ou de la documentation.
   - "plus_tard" : pas le bon moment, recontacter plus tard.
   - "mauvais_interlocuteur" : n'est pas le bon contact, renvoie vers quelqu'un d'autre.
   - "pas_interesse" : refus clair, ne pas insister.
   - "absence" : réponse automatique (absence, congés, ne plus contacter automatique).
   - "autre" : ne rentre dans aucune des cases ci-dessus.
2. RÉDIGE un brouillon de réponse en français, professionnel, chaleureux et CONCIS
   (4-8 lignes), adapté à la catégorie : oriente vers la prochaine étape concrète si
   intérêt (proposer un échange court), réponds à la question si info, reste courtois
   et bref si refus. Signe « L'équipe RénoBoost ». N'invente aucun chiffre ni engagement.

Réponds UNIQUEMENT par un objet JSON valide, sans texte autour :
{"categorie":"<une des clés ci-dessus>","confiance":<0-100>,"sujet":"<objet de la réponse>","brouillon":"<le texte de la réponse>"}`;
}

function parseJson(text: string): Record<string, unknown> | null {
  try {
    return JSON.parse(text);
  } catch {
    const a = text.indexOf("{");
    const b = text.lastIndexOf("}");
    if (a !== -1 && b > a) {
      try {
        return JSON.parse(text.slice(a, b + 1));
      } catch {
        return null;
      }
    }
    return null;
  }
}

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
  const force: boolean = body?.force === true;
  if (!leadId) {
    return NextResponse.json({ error: "leadId manquant." }, { status: 400 });
  }

  // Fil de conversation + dernier message entrant.
  const { data: msgData } = await supabase
    .from("lead_messages")
    .select("*")
    .eq("lead_id", leadId)
    .order("at", { ascending: true });
  const thread = (msgData as LeadMessage[] | null) ?? [];
  const dernierEntrant = [...thread].reverse().find((m) => m.direction === "in");
  if (!dernierEntrant) {
    return NextResponse.json({ error: "Aucune réponse du prospect à analyser." }, { status: 400 });
  }

  // Cache : une suggestion par message entrant.
  if (!force) {
    const { data: cached } = await supabase
      .from("lead_reply_suggestions")
      .select("*")
      .eq("in_message_id", dernierEntrant.id)
      .maybeSingle();
    if (cached) return NextResponse.json({ suggestion: cached, cached: true });
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
    .select("entreprise, contact_nom, verticale:verticales(nom)")
    .eq("id", leadId)
    .maybeSingle();
  if (!lead) {
    return NextResponse.json({ error: "Lead introuvable." }, { status: 404 });
  }
  const verticaleRaw = (lead as { verticale?: { nom?: string } | { nom?: string }[] }).verticale;
  const verticale = Array.isArray(verticaleRaw)
    ? verticaleRaw[0]?.nom ?? null
    : verticaleRaw?.nom ?? null;

  try {
    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: MODEL,
        max_tokens: MAX_TOKENS,
        messages: [
          {
            role: "user",
            content: buildPrompt(
              (lead as { entreprise: string }).entreprise,
              verticale,
              (lead as { contact_nom: string | null }).contact_nom,
              thread,
            ),
          },
        ],
      }),
    });
    if (!res.ok) {
      console.error("reply-draft Anthropic error", res.status, await res.text());
      return NextResponse.json({ error: "Génération indisponible." }, { status: 502 });
    }
    const data = await res.json();
    const text = (Array.isArray(data.content) ? data.content : [])
      .filter((b: Record<string, unknown>) => b.type === "text")
      .map((b: Record<string, unknown>) => b.text as string)
      .join("\n");
    const parsed = parseJson(text);
    if (!parsed || typeof parsed.brouillon !== "string") {
      return NextResponse.json({ error: "Réponse du modèle illisible." }, { status: 502 });
    }
    const categorie = (CATEGORIES as string[]).includes(parsed.categorie as string)
      ? (parsed.categorie as ReplyCategorie)
      : "autre";
    const confiance =
      typeof parsed.confiance === "number"
        ? Math.max(0, Math.min(100, Math.round(parsed.confiance)))
        : null;

    // Remplace toute suggestion existante pour ce message (cas force).
    await supabase.from("lead_reply_suggestions").delete().eq("in_message_id", dernierEntrant.id);
    const { data: inserted, error: insErr } = await supabase
      .from("lead_reply_suggestions")
      .insert({
        lead_id: leadId,
        in_message_id: dernierEntrant.id,
        categorie,
        confiance,
        sujet: typeof parsed.sujet === "string" ? parsed.sujet : null,
        brouillon: parsed.brouillon,
      })
      .select("*")
      .single();
    if (insErr) return NextResponse.json({ error: insErr.message }, { status: 500 });

    return NextResponse.json({ suggestion: inserted, cached: false });
  } catch (e) {
    console.error("reply-draft error", e);
    return NextResponse.json({ error: "Erreur interne." }, { status: 500 });
  }
}
