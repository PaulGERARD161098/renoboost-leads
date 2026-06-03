import type { SupabaseClient } from "@supabase/supabase-js";

// Ingestion serveur des bornes de recharge depuis l'open-data IRVE (fichier
// consolidé national data.gouv, CSV ';'). Exécutée sur Vercel (accès internet).
// Parsing incrémental + upsert par lots : la progression persiste même si le
// gros fichier dépasse le temps imparti. Rossini/Chargemap ne sont PAS ingérés
// (accès en simples liens sur la fiche).

const IRVE_CSV_URL =
  process.env.BORNES_IRVE_URL ||
  "https://www.data.gouv.fr/fr/datasets/r/eb76d20a-8501-400e-b336-d85724de5435";

const UA = { "User-Agent": "renoboost-leads/1.0 (ingestion bornes IRVE)" };
const BATCH = 1000;

type Borne = {
  source: "irve";
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
  raw: null;
};

function num(v: unknown): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(String(v).replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

// Parse le CSV champ par champ (quote-aware) et émet chaque ligne via onRow,
// sans construire un tableau géant (mémoire maîtrisée).
function forEachCsvRow(
  text: string,
  delim: string,
  onRow: (row: Record<string, string>) => void,
): number {
  let header: string[] | null = null;
  let field = "";
  let row: string[] = [];
  let inQuotes = false;
  let count = 0;

  const flushRow = () => {
    row.push(field);
    field = "";
    if (!header) {
      header = row;
    } else if (row.length > 1 || row[0] !== "") {
      const o: Record<string, string> = {};
      header.forEach((h, i) => (o[h] = row[i] ?? ""));
      onRow(o);
      count++;
    }
    row = [];
  };

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
      flushRow();
    } else field += c;
  }
  if (field !== "" || row.length) flushRow();
  return count;
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

  let lus = 0;
  let geocodes = 0;
  let inserted = 0;
  let errors = 0;
  let batch: Borne[] = [];

  const flush = async () => {
    if (!batch.length) return;
    const { error } = await admin
      .from("bornes_recharge")
      .upsert(batch, { onConflict: "source,source_id" });
    if (error) {
      errors += batch.length;
      console.error("IRVE upsert", error.message);
    } else inserted += batch.length;
    batch = [];
  };

  // Dédoublonnage par identifiant : le fichier IRVE contient des clés en double
  // (mêmes id_pdc_itinerance, ou points co-localisés via le repli lat,lng). Sans
  // ça, un lot contenant deux fois la même clé fait échouer tout le lot à l'upsert
  // (ON CONFLICT ... cannot affect row a second time).
  const byId = new Map<string, Borne>();
  lus = forEachCsvRow(text, delim, (r) => {
    const b = mapIrve(r);
    if (b) {
      geocodes++;
      byId.set(b.source_id, b);
    }
  });
  for (const b of byId.values()) {
    batch.push(b);
    if (batch.length >= BATCH) await flush();
  }
  await flush();

  return { source: "irve", lus, geocodes, uniques: byId.size, inserted, errors };
}
