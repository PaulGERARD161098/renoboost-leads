import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MODEL = "claude-haiku-4-5";
const R = 6378137; // rayon terrestre (Web Mercator)
const DEMI_COTE_M = 130; // demi-côté de la vue (~260 m de large)

function toMercator(lon: number, lat: number): [number, number] {
  const x = R * (lon * Math.PI) / 180;
  const y = R * Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
  return [x, y];
}

function ignUrl(lat: number, lon: number): string {
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

export async function POST(req: NextRequest) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Non authentifié." }, { status: 401 });

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey)
    return NextResponse.json({
      error: "Analyse indisponible : ANTHROPIC_API_KEY manquante côté serveur.",
    });

  const body = await req.json().catch(() => null);
  const leadId = body?.leadId;
  if (typeof leadId !== "string")
    return NextResponse.json({ error: "leadId manquant." }, { status: 400 });

  const { data: lead } = await supabase
    .from("leads")
    .select("id, entreprise, adresse, ville, code_postal, latitude, longitude")
    .eq("id", leadId)
    .single();
  if (!lead) return NextResponse.json({ error: "Lead introuvable." }, { status: 404 });

  // 1) Coordonnées : déjà connues, sinon géocodage BAN (gratuit, sans clé).
  let lat = lead.latitude as number | null;
  let lon = lead.longitude as number | null;
  if (lat == null || lon == null) {
    const q = [lead.adresse || lead.entreprise, lead.ville].filter(Boolean).join(" ");
    if (!q.trim())
      return NextResponse.json({ error: "Pas d'adresse pour localiser ce lead." });
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
      return NextResponse.json({ error: "Localisation impossible (géocodage échoué)." });
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
    return NextResponse.json({ error: "Image satellite indisponible pour ce point." });
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
      return NextResponse.json({ error: "Analyse IA momentanément indisponible." }, { status: 502 });
    }
    const data = await res.json();
    const text = (data.content ?? [])
      .filter((b: { type: string }) => b.type === "text")
      .map((b: { text: string }) => b.text)
      .join("\n");
    const parsed = parseJson(text);
    if (!parsed)
      return NextResponse.json({ error: "Réponse IA illisible, réessaie." }, { status: 502 });

    const result = { ...parsed, image_url: imageUrl, analyse_le: new Date().toISOString() };
    await supabase.from("leads").update({ vision_satellite: result }).eq("id", leadId);
    return NextResponse.json({ ok: true, result });
  } catch (e) {
    console.error("vision error", e);
    return NextResponse.json({ error: "Erreur lors de l'analyse." }, { status: 500 });
  }
}
