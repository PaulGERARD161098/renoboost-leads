import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MODEL = "claude-sonnet-4-6";
const MAX_TOKENS = 700;

type Mode = "approche" | "relance";

function buildPrompt(
  mode: Mode,
  lead: {
    entreprise: string;
    ville: string | null;
    secteur: string | null;
    effectif: string | null;
    contact_nom: string | null;
    score_raison: string | null;
  },
  offre: string | null,
  calendlyUrl: string | null,
): string {
  const fiche = [
    `Entreprise : ${lead.entreprise}`,
    lead.secteur ? `Secteur : ${lead.secteur}` : null,
    lead.ville ? `Ville : ${lead.ville}` : null,
    lead.effectif ? `Effectif : ${lead.effectif}` : null,
    lead.contact_nom ? `Contact : ${lead.contact_nom}` : null,
    lead.score_raison ? `Angle d'accroche détecté : ${lead.score_raison}` : null,
  ]
    .filter(Boolean)
    .join("\n");

  const consigneRdv = calendlyUrl
    ? ` Termine en proposant un échange court et insère ce lien de réservation tel quel : ${calendlyUrl}.`
    : " Termine en proposant un échange court de 15 minutes.";

  if (mode === "relance") {
    return `Tu es l'assistant commercial de RénoBoost${
      offre ? ` (offre : ${offre})` : ""
    }. Rédige une RELANCE courte et non insistante à un premier email resté sans réponse, pour ce prospect B2B :

${fiche}

Contraintes : français, ton professionnel et chaleureux, TRÈS concis (3-5 lignes), rappelle l'objet en une phrase, apporte une raison de répondre, sans culpabiliser.${consigneRdv} Signe « L'équipe RénoBoost ». N'invente aucun chiffre.

Réponds UNIQUEMENT par un objet JSON valide : {"sujet":"<objet>","corps":"<le texte>"}`;
  }

  return `Tu es l'assistant commercial de RénoBoost${
    offre ? ` (offre : ${offre})` : ""
  }. Rédige un premier email d'APPROCHE (cold email) personnalisé pour ce prospect B2B :

${fiche}

Contraintes : français, ton professionnel et chaleureux, concis (6-10 lignes), personnalise avec le secteur/angle d'accroche, va à l'essentiel sur la valeur concrète.${consigneRdv} Signe « L'équipe RénoBoost ». N'invente aucun chiffre ni engagement.

Réponds UNIQUEMENT par un objet JSON valide : {"sujet":"<objet>","corps":"<le texte>"}`;
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
  const mode: Mode = body?.mode === "relance" ? "relance" : "approche";
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
      "entreprise, ville, effectif, contact_nom, libelle_naf, naf, score_raison, verticale:verticales(nom)",
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
    verticale?: { nom?: string } | { nom?: string }[];
  };
  const offre = Array.isArray(ld.verticale)
    ? ld.verticale[0]?.nom ?? null
    : ld.verticale?.nom ?? null;

  const { data: ctx } = await supabase
    .from("app_context")
    .select("calendly_url")
    .eq("id", "main")
    .maybeSingle();
  const calendlyUrl = (ctx as { calendly_url: string | null } | null)?.calendly_url ?? null;

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
              mode,
              {
                entreprise: ld.entreprise,
                ville: ld.ville,
                secteur: ld.libelle_naf ?? ld.naf,
                effectif: ld.effectif,
                contact_nom: ld.contact_nom,
                score_raison: ld.score_raison,
              },
              offre,
              calendlyUrl,
            ),
          },
        ],
      }),
    });
    if (!res.ok) {
      console.error("outreach-draft Anthropic error", res.status, await res.text());
      return NextResponse.json({ error: "Génération indisponible." }, { status: 502 });
    }
    const data = await res.json();
    const text = (Array.isArray(data.content) ? data.content : [])
      .filter((b: Record<string, unknown>) => b.type === "text")
      .map((b: Record<string, unknown>) => b.text as string)
      .join("\n");
    const parsed = parseJson(text);
    if (!parsed || typeof parsed.corps !== "string") {
      return NextResponse.json({ error: "Réponse du modèle illisible." }, { status: 502 });
    }
    return NextResponse.json({
      sujet: typeof parsed.sujet === "string" ? parsed.sujet : "",
      corps: parsed.corps,
    });
  } catch (e) {
    console.error("outreach-draft error", e);
    return NextResponse.json({ error: "Erreur interne." }, { status: 500 });
  }
}
