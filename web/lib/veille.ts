import type { SupabaseClient } from "@supabase/supabase-js";

// Veille d'intentions : l'agent cherche le web (web search de Claude) pour des
// signaux d'achat sur le périmètre des cibles, en deux temps (large puis affiné),
// et renvoie des "signaux-leads" qualifiés et orientés prise de contact.

const MODEL = process.env.VEILLE_MODEL || "claude-haiku-4-5";
const DEPARTEMENTS = "Nord (59), Pas-de-Calais (62), Somme (80), Aisne (02), Oise (60)";

type Signal = {
  entreprise: string;
  ville?: string | null;
  type?: string | null;
  declencheur?: string | null;
  resume?: string | null;
  source_url?: string | null;
  source_date?: string | null;
  score_intention?: number | null;
  score_fit?: number | null;
  angle?: string | null;
};

function parseArray(text: string): Signal[] | null {
  const tryParse = (s: string) => {
    try {
      const v = JSON.parse(s);
      return Array.isArray(v) ? (v as Signal[]) : null;
    } catch {
      return null;
    }
  };
  const direct = tryParse(text);
  if (direct) return direct;
  const m = text.match(/\[[\s\S]*\]/);
  return m ? tryParse(m[0]) : null;
}

export async function runVeille(
  supabase: SupabaseClient,
): Promise<{ error: string } | { ok: true; inserted: number; total: number }> {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) return { error: "ANTHROPIC_API_KEY manquante côté serveur." };

  // Thèmes alignés sur les cibles actives.
  const { data: vData } = await supabase
    .from("verticales")
    .select("nom, config")
    .eq("active", true);
  const themesCibles = ((vData as { nom: string; config: Record<string, unknown> }[]) ?? [])
    .map((v) => v.nom)
    .join(" ; ");

  const prompt = `Tu es analyste en intelligence commerciale pour une société qui vend aux PME/ETI : solaire en toiture (autoconsommation), ombrières photovoltaïques de parking, et solutions d'électrification de flotte / bornes IRVE.

OBJECTIF : trouver sur le web des SIGNAUX D'INTENTION récents (30 derniers jours de préférence) indiquant qu'une entreprise du périmètre ${DEPARTEMENTS} :
- passe sa flotte en véhicules électriques / installe des bornes IRVE,
- installe ou projette des ombrières photovoltaïques,
- électrifie ou solarise son site / lance un projet d'autoconsommation,
- ou tout déclencheur foncier pertinent (nouvelle implantation logistique, grand entrepôt, agrandissement).

Cibles actives de l'outil (pour affiner la pertinence) : ${themesCibles || "PME industrielles/logistiques Hauts-de-France"}.

MÉTHODE EN DEUX TEMPS :
1) Recherches larges sur ces thèmes + région (presse économique locale, communiqués, marchés publics, aides ADEME, actualités d'entreprises).
2) Pour chaque piste sérieuse, recherche complémentaire pour CONFIRMER l'entreprise, sa ville, et le déclencheur daté AVEC sa source.

Ne garde que des signaux VÉRIFIABLES (URL source réelle). Évite le bruit et les généralités.

RÉPONDS UNIQUEMENT par un tableau JSON (sans texte autour) :
[{"entreprise":"...","ville":"...","type":"ve_flotte|ombrieres|electrification|irve|autre","declencheur":"événement daté, le pourquoi maintenant","resume":"1-2 phrases","source_url":"https://...","source_date":"AAAA-MM-JJ ou approx","score_intention":0-100,"score_fit":0-100,"angle":"accroche de prise de contact qui référence le déclencheur"}]
score_fit = adéquation avec nos offres (solaire/ombrières/IRVE). Maximum 10 signaux, les plus chauds. Si rien de fiable, renvoie [].`;

  let signaux: Signal[] = [];
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
        max_tokens: 4000,
        tools: [{ type: "web_search_20250305", name: "web_search", max_uses: 10 }],
        messages: [{ role: "user", content: prompt }],
      }),
    });
    if (!res.ok) {
      const detail = await res.text();
      console.error("Veille web search", res.status, detail);
      return {
        error:
          "Recherche web indisponible (l'outil web search n'est peut-être pas activé sur le compte Anthropic).",
      };
    }
    const data = await res.json();
    const text = (data.content ?? [])
      .filter((b: { type: string }) => b.type === "text")
      .map((b: { text: string }) => b.text)
      .join("\n");
    signaux = parseArray(text) ?? [];
  } catch (e) {
    console.error("Veille error", e);
    return { error: "Erreur pendant la veille." };
  }

  if (signaux.length === 0) return { ok: true, inserted: 0, total: 0 };

  // Dédoublonnage vs signaux récents déjà en base.
  const { data: recent } = await supabase
    .from("veille_signaux")
    .select("entreprise, source_url")
    .order("created_at", { ascending: false })
    .limit(500);
  const vusUrl = new Set(
    ((recent as { source_url: string | null }[]) ?? [])
      .map((r) => (r.source_url || "").trim())
      .filter(Boolean),
  );
  const vusEntreprise = new Set(
    ((recent as { entreprise: string }[]) ?? []).map((r) =>
      (r.entreprise || "").trim().toLowerCase(),
    ),
  );

  const aInserer = signaux
    .filter((s) => s.entreprise && s.entreprise.trim())
    .filter((s) => {
      const url = (s.source_url || "").trim();
      const ent = s.entreprise.trim().toLowerCase();
      if (url && vusUrl.has(url)) return false;
      if (vusEntreprise.has(ent)) return false;
      return true;
    })
    .slice(0, 15)
    .map((s) => ({
      entreprise: s.entreprise.trim(),
      ville: s.ville ?? null,
      type: s.type ?? "autre",
      declencheur: s.declencheur ?? null,
      resume: s.resume ?? null,
      source_url: s.source_url ?? null,
      source_date: s.source_date ?? null,
      score_intention:
        typeof s.score_intention === "number" ? s.score_intention : null,
      score_fit: typeof s.score_fit === "number" ? s.score_fit : null,
      angle: s.angle ?? null,
      statut: "nouveau",
    }));

  if (aInserer.length === 0) return { ok: true, inserted: 0, total: signaux.length };
  const { error } = await supabase.from("veille_signaux").insert(aInserer);
  if (error) return { error: error.message };
  return { ok: true, inserted: aInserer.length, total: signaux.length };
}
