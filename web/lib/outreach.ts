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
  // Analyse `vision_satellite` brute (3 potentiels /10 en v2). L'outreach en
  // dérive l'angle terrain ; null/absent → mail strictement comme avant.
  vision?: Record<string, unknown> | null;
};

// Parse un nombre tolérant (number direct ou string numérique), sinon null.
function num(v: unknown): number | null {
  return typeof v === "number"
    ? v
    : typeof v === "string" && v.trim() !== "" && !Number.isNaN(Number(v))
      ? Number(v)
      : null;
}

// Extrait les éléments solaires exploitables de `vision_satellite` (analyse IGN+IA).
// Renvoie null si rien d'exploitable — l'outreach reste alors strictement comme avant.
export function solaireFromVision(
  vision: Record<string, unknown> | null | undefined,
): Solaire {
  if (!vision || typeof vision !== "object") return null;

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

// --- Angle terrain v2 : piloté par les 3 potentiels /10 -----------------------

type PotentielLu = {
  cle: "solaire" | "ombrieres" | "bornes";
  label: string;
  score: number;
  justification: string | null;
};

const POTENTIELS_DEF: { cle: PotentielLu["cle"]; label: string }[] = [
  { cle: "solaire", label: "🔆 Solaire (toiture)" },
  { cle: "ombrieres", label: "🅿️ Ombrières (parking)" },
  { cle: "bornes", label: "🔌 Bornes de recharge VE" },
];

// Lit les 3 potentiels /10 de `vision_satellite` (format v2). Renvoie la liste
// (scores + justifications déjà rédigées côté moteur) et le meilleur potentiel.
// null si la vision n'est pas en v2 ou ne contient aucun score exploitable.
function potentielsV2(
  vision: Record<string, unknown> | null | undefined,
): { liste: PotentielLu[]; meilleur: PotentielLu } | null {
  if (!vision || typeof vision !== "object") return null;
  if ((vision as { version?: number }).version !== 2) return null;

  const liste: PotentielLu[] = [];
  for (const def of POTENTIELS_DEF) {
    const sub = (vision as Record<string, unknown>)[def.cle];
    if (!sub || typeof sub !== "object") continue;
    const score = num((sub as Record<string, unknown>).score);
    if (score == null) continue;
    const just = (sub as Record<string, unknown>).justification;
    liste.push({
      cle: def.cle,
      label: def.label,
      score,
      justification: typeof just === "string" && just.trim() ? just.trim() : null,
    });
  }
  if (liste.length === 0) return null;

  const meilleurCle = (vision as { meilleur?: unknown }).meilleur;
  const meilleur =
    liste.find((p) => p.cle === meilleurCle) ??
    liste.reduce((a, b) => (b.score > a.score ? b : a));
  return { liste, meilleur };
}

// Angle retenu pour piloter le mail — renvoyé à l'UI pour que l'utilisateur
// sache si le brouillon s'appuie sur l'analyse du site (et sur quel axe) ou non.
export type AngleOutreach =
  | { pilote: true; label: string; score: number }
  | { pilote: false };

export function angleOutreach(
  vision: Record<string, unknown> | null | undefined,
): AngleOutreach {
  const p = potentielsV2(vision);
  if (!p) return { pilote: false };
  return { pilote: true, label: p.meilleur.label, score: p.meilleur.score };
}

// Construit le bloc « potentiels détectés » + la consigne d'angle pour le prompt.
function blocsPotentiels(
  vision: Record<string, unknown> | null | undefined,
): { bloc: string; consigne: string } | null {
  const p = potentielsV2(vision);
  if (!p) return null;
  const lignes = p.liste
    .map((x) => `- ${x.label} : ${x.score}/10${x.justification ? ` — ${x.justification}` : ""}`)
    .join("\n");
  const bloc =
    `\n\nPotentiels du site détectés par analyse de vue aérienne (ESTIMATION — ` +
    `ordres de grandeur, jamais des mesures certifiées) :\n${lignes}\n` +
    `Potentiel à mettre en avant en priorité : ${p.meilleur.label} (${p.meilleur.score}/10).`;
  // Retour terrain (Henry) : un mail vantait les ombrières d'un site noté 0/10 en
  // ombrières. On verrouille : interdiction explicite des axes faibles, et les
  // potentiels (analyse la plus récente du site) priment sur l'angle d'accroche.
  const faibles = p.liste.filter((x) => x.score < 4 && x.cle !== p.meilleur.cle);
  const interdit = faibles.length
    ? ` INTERDIT de mettre en avant : ${faibles
        .map((x) => `${x.label} (${x.score}/10)`)
        .join(", ")} — n'en parle pas, même si l'offre ou l'angle d'accroche les évoque.`
    : "";
  const consigne =
    ` Construis l'accroche autour du potentiel le plus fort ci-dessus et relie-le ` +
    `concrètement à l'offre. N'évoque les autres potentiels que s'ils sont eux aussi ` +
    `élevés (≥6/10) ET cohérents avec l'offre ; ignore les potentiels à faible score.` +
    interdit +
    ` Si l'« angle d'accroche détecté » contredit ces potentiels, ce sont les ` +
    `potentiels ci-dessus (analyse la plus récente du site) qui priment. ` +
    `Pour le potentiel « bornes de recharge », appuie-toi sur la dynamique ` +
    `d'électrification de la zone (présence/absence de bornes alentour) telle qu'indiquée. ` +
    `Formule toute surface ou quantité en ordre de grandeur prudent (« de l'ordre de », ` +
    `« environ »), jamais comme une mesure exacte.`;
  return { bloc, consigne };
}

export function buildOutreachPrompt(
  mode: OutreachMode,
  lead: LeadFiche,
  offre: string | null,
  calendlyUrl: string | null,
  client: string | null = null,
  telephone: string | null = null,
): string {
  // Quand la campagne est affectée à un client, l'email est rédigé et signé en
  // son nom (RénoBoost reste l'outil, le client est l'émetteur visible).
  const marque = client?.trim() || "RénoBoost";
  const signature = telephone?.trim()
    ? `Signe « L'équipe ${marque} » et ajoute ce numéro de téléphone tel quel sous la signature : ${telephone.trim()}.`
    : `Signe « L'équipe ${marque} ».`;
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

  // Angle terrain : on privilégie les 3 potentiels /10 (v2) pour piloter le mail
  // par le potentiel le plus fort + l'offre. Repli sur l'estimation brute (v1).
  const potentiels = blocsPotentiels(lead.vision);
  let blocTerrain = "";
  let consigneTerrain = "";
  if (potentiels) {
    blocTerrain = potentiels.bloc;
    consigneTerrain = potentiels.consigne;
  } else {
    const terrain = formatTerrain(solaireFromVision(lead.vision));
    if (terrain) {
      blocTerrain = `\n\nÉléments terrain (ESTIMATION depuis vue aérienne — ordres de grandeur, jamais des mesures certifiées) : ${terrain}.`;
      consigneTerrain =
        " Tu peux t'appuyer sur les éléments terrain pour personnaliser l'accroche, mais formule-les en ordre de grandeur prudent (« de l'ordre de », « environ ») et jamais comme une mesure exacte.";
    }
  }

  const consigneRdv = calendlyUrl
    ? ` Termine en proposant un échange court et insère ce lien de réservation tel quel : ${calendlyUrl}.`
    : " Termine en proposant un échange court de 15 minutes.";

  if (mode === "relance") {
    return `Tu es l'assistant commercial de ${marque}${
      offre ? ` (offre : ${offre})` : ""
    }. Rédige une RELANCE courte et non insistante à un premier email resté sans réponse, pour ce prospect B2B :

${fiche}${blocTerrain}

Contraintes : français, ton professionnel et chaleureux, TRÈS concis (3-5 lignes), rappelle l'objet en une phrase, apporte une raison de répondre, sans culpabiliser.${consigneTerrain}${consigneRdv} ${signature} N'invente aucun chiffre.

Réponds UNIQUEMENT par un objet JSON valide : {"sujet":"<objet>","corps":"<le texte>"}`;
  }

  return `Tu es l'assistant commercial de ${marque}${
    offre ? ` (offre : ${offre})` : ""
  }. Rédige un premier email d'APPROCHE (cold email) personnalisé pour ce prospect B2B :

${fiche}${blocTerrain}

Contraintes : français, ton professionnel et chaleureux, concis (6-10 lignes), personnalise avec le secteur/angle d'accroche, va à l'essentiel sur la valeur concrète.${consigneTerrain}${consigneRdv} ${signature} N'invente aucun chiffre ni engagement.

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
  client: string | null = null,
  telephone: string | null = null,
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
          {
            role: "user",
            content: buildOutreachPrompt(mode, lead, offre, calendlyUrl, client, telephone),
          },
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
