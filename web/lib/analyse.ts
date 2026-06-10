// Analyse d'image (capture satellite GMaps ou upload) par Claude Vision.
// Extrait : entreprises visibles (panneaux/enseignes), caractéristiques du
// bâti (toiture, parking, ombrières, bornes VE), opportunités commerciales
// (énergie/solaire/IRVE), accroche prête à l'envoi.
//
// Format de sortie volontairement structuré pour pouvoir être rendu sans
// retraitement côté UI (et plus tard pour alimenter veille → lead).

import {
  assembler,
  niveauPourScore,
  scorerBornes,
  scorerOmbrieres,
  scorerSolaire,
  surfaceExploitableDepuis,
  type AnalysePotentiels,
  type ComptageBornes,
} from "@/lib/potentiel";

export const ANALYSE_MODEL = "claude-sonnet-4-6";
const MAX_TOKENS = 1500;

export type AnalyseContext = {
  address: string | null;
  lat: number | null;
  lng: number | null;
  zoom: number | null;
  source: "capture" | "upload";
};

export type AnalyseResult = {
  resume: string;
  entreprises: Array<{
    nom: string;
    secteur?: string | null;
    indices?: string | null;
  }>;
  terrain: {
    toiture?: { surface_m2_estimee?: number | null; type?: string | null; notes?: string | null };
    parking?: { surface_m2_estimee?: number | null; nb_places_estimee?: number | null; ombrieres_existantes?: boolean | null };
    bornes_ve?: { presentes?: boolean | null; nb_estime?: number | null };
    autres?: string | null;
  };
  opportunites: Array<{ angle: string; pourquoi: string; priorite: "haute" | "moyenne" | "basse" }>;
  accroche: { sujet: string; corps: string } | null;
};

export function buildAnalysePrompt(ctx: AnalyseContext): string {
  const lieu = [
    ctx.address ? `Adresse : ${ctx.address}` : null,
    ctx.lat != null && ctx.lng != null
      ? `Coordonnées : ${ctx.lat.toFixed(5)}, ${ctx.lng.toFixed(5)}`
      : null,
    ctx.zoom != null ? `Zoom carte : ${ctx.zoom}` : null,
    `Source : ${ctx.source === "capture" ? "capture Google Maps satellite" : "upload manuel"}`,
  ]
    .filter(Boolean)
    .join(" · ");

  return `Tu es l'assistant commercial de RénoBoost (offres : solaire toiture, ombrières de parking, bornes de recharge VE). On t'envoie une image — vue aérienne / satellite / capture d'une zone d'activité — pour t'aider à identifier des **opportunités commerciales B2B**.

${lieu}

Analyse l'image avec rigueur (n'invente rien, ordre de grandeur si tu mesures, marque "inconnu" si non visible) et renvoie UNIQUEMENT un objet JSON valide, sans texte autour, au schéma exact :

{
  "resume": "<2-3 phrases : ce qu'on voit en synthèse, l'opportunité principale>",
  "entreprises": [
    { "nom": "<nom lu sur l'image OU nom probable basé sur l'adresse>", "secteur": "<si déductible>", "indices": "<panneau, logo, enseigne, type de bâtiment>" }
  ],
  "terrain": {
    "toiture": { "surface_m2_estimee": <nombre ou null>, "type": "<plate|inclinée|métallique|tuile|inconnu>", "notes": "<obstructions, orientation, état>" },
    "parking": { "surface_m2_estimee": <nombre ou null>, "nb_places_estimee": <nombre ou null>, "ombrieres_existantes": <true|false|null> },
    "bornes_ve": { "presentes": <true|false|null>, "nb_estime": <nombre ou null> },
    "autres": "<éléments notables : panneaux PV déjà installés, espace vert, voirie, flotte de véhicules visible…>"
  },
  "opportunites": [
    { "angle": "<solaire toiture | ombrières parking | bornes VE | autre>", "pourquoi": "<raison concrète tirée de l'image>", "priorite": "haute|moyenne|basse" }
  ],
  "accroche": { "sujet": "<objet d'email court>", "corps": "<6-10 lignes, ton chaleureux, ordres de grandeur prudents, signe « L'équipe RénoBoost »>" }
}

Contraintes :
- Liste entreprises VIDE si tu ne lis rien d'identifiable sur l'image (ne pas inventer).
- Estimations en m² toujours en ordre de grandeur (arrondi au 100 m² près).
- Si l'image n'est pas une vue aérienne (intérieur, photo de produit, etc.) : remplis resume avec ce constat et laisse les autres champs vides/null.`;
}

// --- Analyse d'image → potentiels v2 ---------------------------------------
// Convertit le `terrain` lu sur l'image en AnalysePotentiels (même format que
// l'analyse satellite), via les mêmes scorers. Le lead créé depuis /analyse
// arrive ainsi pré-scoré et le pipeline mail (outreach) reste cohérent.

/** Vocabulaire du prompt vision ("plate|inclinée|métallique|tuile|inconnu") → clés des scorers. */
function normaliserTypeToiture(brut: string | null | undefined): string {
  const t = (brut ?? "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
  if (t.startsWith("plate") || t.startsWith("plat")) return "plate";
  if (t.startsWith("incline")) return "inclinee";
  return "inconnue";
}

export function potentielsDepuisAnalyse(
  terrain: AnalyseResult["terrain"] | undefined,
  bornes: ComptageBornes,
): AnalysePotentiels {
  const t = terrain ?? {};

  const typeToiture = normaliserTypeToiture(t.toiture?.type);
  const surfaceToiture = t.toiture?.surface_m2_estimee ?? null;
  const solaire = scorerSolaire(
    surfaceExploitableDepuis(surfaceToiture, typeToiture, null),
    surfaceToiture,
    typeToiture === "inconnue" ? (t.toiture?.type ?? null) : typeToiture,
  );

  const parkingPresent =
    (t.parking?.surface_m2_estimee ?? 0) > 0 || (t.parking?.nb_places_estimee ?? 0) > 0;
  let ombrieres = scorerOmbrieres(
    parkingPresent,
    t.parking?.nb_places_estimee ?? null,
    t.parking?.surface_m2_estimee ?? null,
    null,
    null,
  );
  if (t.parking?.ombrieres_existantes === true && ombrieres.score > 1) {
    ombrieres = {
      ...ombrieres,
      score: 1,
      niveau: niveauPourScore(1),
      justification: `${ombrieres.justification} Ombrières déjà présentes — opportunité résiduelle.`,
    };
  }

  const surSiteVision =
    t.bornes_ve?.presentes === true ? Math.max(1, t.bornes_ve?.nb_estime ?? 1) : 0;
  const potBornes = scorerBornes(
    Math.max(bornes.sur_site, surSiteVision),
    bornes.voisinage_1km,
    bornes.rayon_10km,
    false,
    bornes.types,
  );

  const pots = assembler(solaire, ombrieres, potBornes, "");
  delete pots.image_url;
  pots.synthese += " Dérivé d'une analyse d'image Magellan — lance l'analyse satellite pour affiner.";
  return pots;
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

export type VisionDraft =
  | { ok: true; result: AnalyseResult }
  | { ok: false; status: number; error: string };

// Appelle Anthropic en mode vision (image base64) et renvoie le résultat parsé.
export async function runVisionAnalyse(
  apiKey: string,
  imageBase64: string,
  mediaType: "image/png" | "image/jpeg" | "image/webp",
  ctx: AnalyseContext,
): Promise<VisionDraft> {
  try {
    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: ANALYSE_MODEL,
        max_tokens: MAX_TOKENS,
        messages: [
          {
            role: "user",
            content: [
              {
                type: "image",
                source: { type: "base64", media_type: mediaType, data: imageBase64 },
              },
              { type: "text", text: buildAnalysePrompt(ctx) },
            ],
          },
        ],
      }),
    });
    if (!res.ok) {
      console.error("analyse Anthropic error", res.status, await res.text());
      return { ok: false, status: 502, error: "Analyse Vision indisponible." };
    }
    const data = await res.json();
    const text = (Array.isArray(data.content) ? data.content : [])
      .filter((b: Record<string, unknown>) => b.type === "text")
      .map((b: Record<string, unknown>) => b.text as string)
      .join("\n");
    const parsed = parseJson(text);
    if (!parsed) {
      return { ok: false, status: 502, error: "Réponse du modèle illisible." };
    }
    return { ok: true, result: parsed as unknown as AnalyseResult };
  } catch (e) {
    console.error("analyse error", e);
    return { ok: false, status: 500, error: "Erreur interne." };
  }
}
