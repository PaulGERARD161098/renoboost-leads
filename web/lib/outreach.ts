// Génération de brouillons d'emails (approche / relance) via l'API Anthropic.
// Factorisé pour être partagé entre la génération unitaire (api/lead/outreach-draft)
// et la génération EN LOT (api/lead/outreach-draft-batch). Ne persiste rien :
// renvoie {sujet, corps} ; l'appelant décide quoi en faire.

export const OUTREACH_MODEL = "claude-sonnet-4-6";
const MAX_TOKENS = 700;

export type OutreachMode = "approche" | "relance";

export type LeadFiche = {
  entreprise: string;
  ville: string | null;
  secteur: string | null;
  effectif: string | null;
  contact_nom: string | null;
  score_raison: string | null;
};

export function buildOutreachPrompt(
  mode: OutreachMode,
  lead: LeadFiche,
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

export type DraftResult =
  | { ok: true; sujet: string; corps: string }
  | { ok: false; status: number; error: string };

// Appelle Anthropic et renvoie le brouillon parsé. Best-effort : toute erreur
// est renvoyée structurée (jamais d'exception non gérée).
export async function generateOutreachDraft(
  apiKey: string,
  mode: OutreachMode,
  lead: LeadFiche,
  offre: string | null,
  calendlyUrl: string | null,
): Promise<DraftResult> {
  try {
    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: OUTREACH_MODEL,
        max_tokens: MAX_TOKENS,
        messages: [
          { role: "user", content: buildOutreachPrompt(mode, lead, offre, calendlyUrl) },
        ],
      }),
    });
    if (!res.ok) {
      console.error("outreach Anthropic error", res.status, await res.text());
      return { ok: false, status: 502, error: "Génération indisponible." };
    }
    const data = await res.json();
    const text = (Array.isArray(data.content) ? data.content : [])
      .filter((b: Record<string, unknown>) => b.type === "text")
      .map((b: Record<string, unknown>) => b.text as string)
      .join("\n");
    const parsed = parseJson(text);
    if (!parsed || typeof parsed.corps !== "string") {
      return { ok: false, status: 502, error: "Réponse du modèle illisible." };
    }
    return {
      ok: true,
      sujet: typeof parsed.sujet === "string" ? parsed.sujet : "",
      corps: parsed.corps,
    };
  } catch (e) {
    console.error("outreach error", e);
    return { ok: false, status: 500, error: "Erreur interne." };
  }
}
