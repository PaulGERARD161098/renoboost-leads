// Génération de brouillons d'emails (approche / relance) via l'API Anthropic.
// Factorisé pour être partagé entre la génération unitaire (api/lead/outreach-draft)
// et la génération EN LOT (api/lead/outreach-draft-batch). Ne persiste rien :
// renvoie {sujet, corps} ; l'appelant décide quoi en faire.

export const OUTREACH_MODEL = "claude-sonnet-4-6";
const MAX_TOKENS = 700;

export type OutreachMode = "approche" | "relance";

export type Solaire = {
  toiture_m2: number | null;
  toiture_type: string | null;
  parking_m2: number | null;
  ombrieres: boolean | null;
} | null;

export type LeadFiche = {
  entreprise: string;
  ville: string | null;
  secteur: string | null;
  effectif: string | null;
  contact_nom: string | null;
  score_raison: string | null;
  solaire?: Solaire;
};

// Extrait les éléments solaires exploitables de `vision_satellite` (analyse IGN+IA).
// Renvoie null si rien d'exploitable — l'outreach reste alors strictement comme avant.
export function solaireFromVision(
  vision: Record<string, unknown> | null | undefined,
): Solaire {
  if (!vision || typeof vision !== "object") return null;
  const num = (v: unknown): number | null =>
    typeof v === "number"
      ? v
      : typeof v === "string" && v.trim() !== "" && !Number.isNaN(Number(v))
        ? Number(v)
        : null;

  // Format v2 (3 potentiels /10) : on lit solaire + ombrières.
  if ((vision as { version?: number }).version === 2) {
    const sol = (vision.solaire ?? {}) as Record<string, unknown>;
    const omb = (vision.ombrieres ?? {}) as Record<string, unknown>;
    const ombScore = num(omb.score);
    const s2: NonNullable<Solaire> = {
      toiture_m2: num(sol.surface_exploitable_m2) ?? num(sol.surface_toiture_m2),
      toiture_type: typeof sol.type_toiture === "string" ? sol.type_toiture : null,
      parking_m2: num(omb.surface_parking_m2),
      ombrieres: ombScore != null ? ombScore >= 4 : null,
    };
    if (s2.toiture_m2 == null && s2.parking_m2 == null && !s2.ombrieres) return null;
    return s2;
  }

  // Format v1 (rétro-compatibilité).
  const toit = (vision.toiture ?? {}) as Record<string, unknown>;
  const park = (vision.parking ?? {}) as Record<string, unknown>;
  const s: NonNullable<Solaire> = {
    toiture_m2: num(toit.surface_estimee_m2),
    toiture_type: typeof toit.type === "string" ? toit.type : null,
    parking_m2: num(park.surface_estimee_m2),
    ombrieres:
      typeof park.ombrieres_possibles === "boolean" ? park.ombrieres_possibles : null,
  };
  if (s.toiture_m2 == null && s.parking_m2 == null && !s.ombrieres) return null;
  return s;
}

// Arrondi en ordre de grandeur (au 500 m² le plus proche) : on n'avance jamais
// une estimation satellite comme une mesure exacte.
function ordreDeGrandeur(m2: number | null): number | null {
  if (m2 == null || m2 <= 0) return null;
  return Math.max(500, Math.round(m2 / 500) * 500);
}

function formatTerrain(s: Solaire): string | null {
  if (!s) return null;
  const bouts: string[] = [];
  const toit = ordreDeGrandeur(s.toiture_m2);
  if (toit) {
    const t =
      s.toiture_type && s.toiture_type !== "inconnue" ? ` (toiture ${s.toiture_type})` : "";
    bouts.push(`toiture exploitable de l'ordre de ${toit.toLocaleString("fr-FR")} m²${t}`);
  }
  const park = ordreDeGrandeur(s.parking_m2);
  if (park) bouts.push(`parking de l'ordre de ${park.toLocaleString("fr-FR")} m²`);
  if (s.ombrieres) bouts.push("ombrières de parking envisageables");
  return bouts.length ? bouts.join(" ; ") : null;
}

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

  const terrain = formatTerrain(lead.solaire ?? null);
  const blocTerrain = terrain
    ? `\n\nÉléments terrain (ESTIMATION depuis vue aérienne — ordres de grandeur, jamais des mesures certifiées) : ${terrain}.`
    : "";
  const consigneTerrain = terrain
    ? " Tu peux t'appuyer sur les éléments terrain pour personnaliser l'accroche, mais formule-les en ordre de grandeur prudent (« de l'ordre de », « environ ») et jamais comme une mesure exacte."
    : "";

  const consigneRdv = calendlyUrl
    ? ` Termine en proposant un échange court et insère ce lien de réservation tel quel : ${calendlyUrl}.`
    : " Termine en proposant un échange court de 15 minutes.";

  if (mode === "relance") {
    return `Tu es l'assistant commercial de RénoBoost${
      offre ? ` (offre : ${offre})` : ""
    }. Rédige une RELANCE courte et non insistante à un premier email resté sans réponse, pour ce prospect B2B :

${fiche}${blocTerrain}

Contraintes : français, ton professionnel et chaleureux, TRÈS concis (3-5 lignes), rappelle l'objet en une phrase, apporte une raison de répondre, sans culpabiliser.${consigneTerrain}${consigneRdv} Signe « L'équipe RénoBoost ». N'invente aucun chiffre.

Réponds UNIQUEMENT par un objet JSON valide : {"sujet":"<objet>","corps":"<le texte>"}`;
  }

  return `Tu es l'assistant commercial de RénoBoost${
    offre ? ` (offre : ${offre})` : ""
  }. Rédige un premier email d'APPROCHE (cold email) personnalisé pour ce prospect B2B :

${fiche}${blocTerrain}

Contraintes : français, ton professionnel et chaleureux, concis (6-10 lignes), personnalise avec le secteur/angle d'accroche, va à l'essentiel sur la valeur concrète.${consigneTerrain}${consigneRdv} Signe « L'équipe RénoBoost ». N'invente aucun chiffre ni engagement.

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
