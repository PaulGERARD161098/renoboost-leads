import type { SupabaseClient } from "@supabase/supabase-js";

// Ingestion serveur des bornes de recharge (exécutée sur Vercel, qui a l'accès
// internet). Source IRVE (fichier consolidé data.gouv) + Rossini Energy
// (endpoint map_parks). Upsert idempotent sur (source, source_id).

// Fichier consolidé IRVE (CSV ';'). Surchargeable via env BORNES_IRVE_URL.
const IRVE_CSV_URL =
  process.env.BORNES_IRVE_URL ||
  "https://www.data.gouv.fr/fr/datasets/r/eb76d20a-8501-400e-b336-d85724de5435";
const ROSSINI_URL =
  process.env.BORNES_ROSSINI_URL || "https://maps.rossinienergy.com/map_parks/";

const UA = { "User-Agent": "renoboost-leads/1.0 (ingestion bornes)" };
const BATCH = 1000;

type Borne = {
  source: string;
  source_id: string;
  nom_station: string | null;
  operateur: string | null;
  amenageur: string | null;
  enseigne: string | null;
  lat: number | null;
  lng: number | null;
  puissance_kw: number | null;
  nb_points: number | null;
  adresse: string | null;
  code_postal: string | null;
  commune: string | null;
  departement: string | null;
  date_maj: string | null;
  raw: Record<string, unknown> | null;
};

function num(v: unknown): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(String(v).replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

// Parse CSV (gère les champs entre guillemets contenant le délimiteur).
function parseCsv(text: string, delim: string): Record<string, string>[] {
  const rows: string[][] = [];
  let field = "";
  let row: string[] = [];
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else inQuotes = false;
      } else field += c;
    } else if (c === '"') inQuotes = true;
    else if (c === delim) {
      row.push(field);
      field = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      field = "";
      if (row.length > 1 || row[0] !== "") rows.push(row);
      row = [];
    } else field += c;
  }
  if (field !== "" || row.length) {
    row.push(field);
    rows.push(row);
  }
  if (!rows.length) return [];
  const header = rows[0];
  return rows.slice(1).map((r) => {
    const o: Record<string, string> = {};
    header.forEach((h, idx) => (o[h] = r[idx] ?? ""));
    return o;
  });
}

async function upsertAll(
  admin: SupabaseClient,
  rows: Borne[],
): Promise<{ inserted: number; errors: number }> {
  let inserted = 0;
  let errors = 0;
  for (let i = 0; i < rows.length; i += BATCH) {
    const slice = rows.slice(i, i + BATCH);
    const { error } = await admin
      .from("bornes_recharge")
      .upsert(slice, { onConflict: "source,source_id" });
    if (error) {
      errors += slice.length;
      console.error("bornes upsert", error.message);
    } else inserted += slice.length;
  }
  return { inserted, errors };
}

function mapIrve(r: Record<string, string>): Borne | null {
  let lat = num(r.consolidated_latitude ?? r.latitude);
  let lng = num(r.consolidated_longitude ?? r.longitude);
  if ((lat === null || lng === null) && r.coordonneesXY) {
    const parts = r.coordonneesXY
      .replace(/[[\]]/g, "")
      .split(/[;,]/)
      .map((p) => p.trim());
    if (parts.length === 2) {
      lng = num(parts[0]);
      lat = num(parts[1]);
    }
  }
  if (lat === null || lng === null) return null;
  const cp = (r.consolidated_code_postal || r.code_postal || "").trim();
  const sourceId =
    r.id_pdc_itinerance || r.id_station_itinerance || r.id_pdc_local || `${lat},${lng}`;
  return {
    source: "irve",
    source_id: sourceId,
    nom_station: r.nom_station || null,
    operateur: r.nom_operateur || null,
    amenageur: r.nom_amenageur || null,
    enseigne: r.nom_enseigne || null,
    lat,
    lng,
    puissance_kw: num(r.puissance_nominale),
    nb_points: num(r.nbre_pdc),
    adresse: r.adresse_station || null,
    code_postal: cp || null,
    commune: r.consolidated_commune || r.commune || null,
    departement: cp.length >= 2 ? cp.slice(0, 2) : null,
    date_maj: r.date_maj || null,
    raw: null,
  };
}

export async function ingestIrve(admin: SupabaseClient) {
  const res = await fetch(IRVE_CSV_URL, { headers: UA });
  if (!res.ok) throw new Error(`IRVE HTTP ${res.status}`);
  const text = await res.text();
  const delim = text.slice(0, 2000).includes(";") ? ";" : ",";
  const rows = parseCsv(text, delim);
  const bornes: Borne[] = [];
  for (const r of rows) {
    const b = mapIrve(r);
    if (b) bornes.push(b);
  }
  const { inserted, errors } = await upsertAll(admin, bornes);
  return { source: "irve", lus: rows.length, geocodes: bornes.length, inserted, errors };
}

// Mapping tolérant de l'endpoint Rossini map_parks (forme JSON à confirmer).
function mapRossini(item: Record<string, unknown>, idx: number): Borne | null {
  const g = (...keys: string[]): unknown => {
    for (const k of keys) if (item[k] !== undefined && item[k] !== null) return item[k];
    return undefined;
  };
  let lat = num(g("lat", "latitude", "y"));
  let lng = num(g("lng", "lon", "long", "longitude", "x"));
  const coords = g("coordinates", "coords", "lonlat");
  if ((lat === null || lng === null) && Array.isArray(coords) && coords.length === 2) {
    lng = num(coords[0]);
    lat = num(coords[1]);
  }
  const geom = g("geometry") as { coordinates?: unknown } | undefined;
  if ((lat === null || lng === null) && geom && Array.isArray(geom.coordinates)) {
    lng = num(geom.coordinates[0]);
    lat = num(geom.coordinates[1]);
  }
  if (lat === null || lng === null) return null;
  const cp = String(g("code_postal", "postcode", "cp", "zip") ?? "").trim();
  return {
    source: "rossini",
    source_id: String(g("id", "uuid", "slug", "reference") ?? `rossini-${idx}`),
    nom_station: (g("name", "nom", "title", "libelle") as string) ?? null,
    operateur: "Rossini Energy",
    amenageur: "Rossini Energy",
    enseigne: (g("enseigne", "client") as string) ?? null,
    lat,
    lng,
    puissance_kw: num(g("puissance", "power", "puissance_kw")),
    nb_points: num(g("nb_points", "bornes", "nb_bornes")),
    adresse: (g("adresse", "address") as string) ?? null,
    code_postal: cp || null,
    commune: (g("commune", "ville", "city") as string) ?? null,
    departement: cp.length >= 2 ? cp.slice(0, 2) : null,
    date_maj: null,
    raw: item,
  };
}

export async function ingestRossini(admin: SupabaseClient) {
  const res = await fetch(ROSSINI_URL, { headers: { ...UA, Accept: "application/json" } });
  if (!res.ok) throw new Error(`Rossini HTTP ${res.status}`);
  const data = await res.json();
  // L'endpoint peut renvoyer un tableau, ou { features: [...] } / { results: [...] }.
  const items: Record<string, unknown>[] = Array.isArray(data)
    ? data
    : (data.features ?? data.results ?? data.parks ?? data.data ?? []);
  const bornes: Borne[] = [];
  items.forEach((it, idx) => {
    // GeoJSON Feature : fusionne properties + geometry.
    const flat =
      it && typeof it === "object" && "properties" in it
        ? { ...(it.properties as object), geometry: (it as { geometry?: unknown }).geometry }
        : it;
    const b = mapRossini(flat as Record<string, unknown>, idx);
    if (b) bornes.push(b);
  });
  const { inserted, errors } = await upsertAll(admin, bornes);
  return { source: "rossini", lus: items.length, geocodes: bornes.length, inserted, errors };
}
