import type { SupabaseClient } from "@supabase/supabase-js";

// Analyse "potentiel solaire" d'un lead via vue aérienne IGN + Claude Vision.
// Partagé entre la route /api/lead/satellite et l'outil Magellan.

const MODEL = "claude-haiku-4-5";
const R = 6378137; // rayon terrestre (Web Mercator)
const DEMI_COTE_M = 130; // demi-côté de la vue (~260 m de large)

function toMercator(lon: number, lat: number): [number, number] {
  const x = (R * (lon * Math.PI)) / 180;
  const y = R * Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
  return [x, y];
}

export function ignUrl(lat: number, lon: number): string {
  const [x, y] = toMercator(lon, lat);
  const bbox = [x - DEMI_COTE_M, y - DEMI_COTE_M, x + DEMI_COTE_M, y + DEMI_COTE_M].join(",");
  const params = new URLSearchParams({
    SERVICE: "WMS",
    VERSION: "1.3.0",
    REQUEST: "GetMap",
    LAYERS: "ORTHOIMAGERY.ORTHOPHOTOS",
    STYLES: "",
    CRS: "EPSG:3857",
    BBOX: bbox,
    WIDTH: "640",
    HEIGHT: "640",
    FORMAT: "image/jpeg",
  });
  return `https://data.geopf.fr/wms-r/wms?${params.toString()}`;
}

const PROMPT = `Tu analyses une vue aérienne IGN (orthophoto) centrée sur le site d'une entreprise, pour évaluer son potentiel solaire (panneaux en toiture et ombrières de parking).
Réponds UNIQUEMENT par un objet JSON valide, sans texte autour, au format :
{"score":<0-100>,"verdict":"<phrase courte>","toiture":{"presente":<bool>,"type":"plate|inclinee|inconnue","surface_estimee_m2":<number|null>},"parking":{"present":<bool>,"surface_estimee_m2":<number|null>,"ombrieres_possibles":<bool>},"commentaire":"<2-3 phrases>"}
Le score reflète l'intérêt global (grandes surfaces planes = élevé). Sois prudent si l'image est ambiguë.`;

function parseJson(text: string): Record<string, unknown> | null {
  try {
    return JSON.parse(text);
  } catch {
    const m = text.match(/\{[\s\S]*\}/);
    if (m) {
      try {
        return JSON.parse(m[0]);
      } catch {
        return null;
      }
    }
    return null;
  }
}

type AnalyseResult =
  | { error: string }
  | { ok: true; result: Record<string, unknown> };

export async function analyseSatellite(
  supabase: SupabaseClient,
  leadId: string,
): Promise<AnalyseResult> {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey)
    return { error: "Analyse indisponible : ANTHROPIC_API_KEY manquante côté serveur." };

  const { data: lead } = await supabase
    .from("leads")
    .select("id, entreprise, adresse, ville, code_postal, latitude, longitude")
    .eq("id", leadId)
    .single();
  if (!lead) return { error: "Lead introuvable." };

  // 1) Coordonnées : connues, sinon géocodage BAN.
  let lat = lead.latitude as number | null;
  let lon = lead.longitude as number | null;
  if (lat == null || lon == null) {
    const q = [lead.adresse || lead.entreprise, lead.ville].filter(Boolean).join(" ");
    if (!q.trim()) return { error: "Pas d'adresse pour localiser ce lead." };
    const url = new URL("https://api-adresse.data.gouv.fr/search/");
    url.searchParams.set("q", q);
    url.searchParams.set("limit", "1");
    if (lead.code_postal) url.searchParams.set("postcode", String(lead.code_postal));
    try {
      const geo = await fetch(url.toString());
      const gj = await geo.json();
      const coords = gj?.features?.[0]?.geometry?.coordinates;
      if (Array.isArray(coords)) {
        lon = coords[0];
        lat = coords[1];
      }
    } catch {
      /* ignore */
    }
    if (lat == null || lon == null)
      return { error: "Localisation impossible (géocodage échoué)." };
    await supabase.from("leads").update({ latitude: lat, longitude: lon }).eq("id", leadId);
  }

  const imageUrl = ignUrl(lat, lon);

  // 2) Image IGN → base64.
  let b64: string;
  try {
    const img = await fetch(imageUrl);
    if (!img.ok) throw new Error(`IGN ${img.status}`);
    const buf = Buffer.from(await img.arrayBuffer());
    if (buf.length < 1000) throw new Error("image vide");
    b64 = buf.toString("base64");
  } catch (e) {
    console.error("IGN fetch", e);
    return { error: "Image satellite indisponible pour ce point." };
  }

  // 3) Claude Vision.
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
        max_tokens: 700,
        messages: [
          {
            role: "user",
            content: [
              {
                type: "image",
                source: { type: "base64", media_type: "image/jpeg", data: b64 },
              },
              { type: "text", text: PROMPT },
            ],
          },
        ],
      }),
    });
    if (!res.ok) {
      console.error("Anthropic vision", res.status, await res.text());
      return { error: "Analyse IA momentanément indisponible." };
    }
    const data = await res.json();
    const text = (data.content ?? [])
      .filter((b: { type: string }) => b.type === "text")
      .map((b: { text: string }) => b.text)
      .join("\n");
    const parsed = parseJson(text);
    if (!parsed) return { error: "Réponse IA illisible, réessaie." };

    const result = { ...parsed, image_url: imageUrl, analyse_le: new Date().toISOString() };
    await supabase.from("leads").update({ vision_satellite: result }).eq("id", leadId);
    return { ok: true, result };
  } catch (e) {
    console.error("vision error", e);
    return { error: "Erreur lors de l'analyse." };
  }
}
