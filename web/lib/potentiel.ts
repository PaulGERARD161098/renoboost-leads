// Analyse des 3 potentiels (solaire / ombrières / bornes) côté web — miroir TS
// du moteur Python `renoboost_leads.potentiel`. Sert la voie on-demand
// (/api/lead/satellite) pour produire le même format v2 que le worker.

export type PotentielSolaire = {
  score: number;
  niveau: string;
  surface_toiture_m2: number | null;
  surface_exploitable_m2: number | null;
  type_toiture: string | null;
  justification: string;
};
export type PotentielOmbrieres = {
  score: number;
  niveau: string;
  surface_parking_m2: number | null;
  nb_places: number | null;
  partage: boolean | null;
  exploitant_probable: string | null;
  justification: string;
};
export type PotentielBornes = {
  score: number;
  niveau: string;
  sur_site: number;
  voisinage_1km: number;
  rayon_10km: number;
  types: string[];
  justification: string;
};
export type AnalysePotentiels = {
  version: 2;
  solaire: PotentielSolaire;
  ombrieres: PotentielOmbrieres;
  bornes: PotentielBornes;
  meilleur: "solaire" | "ombrieres" | "bornes";
  synthese: string;
  image_url?: string;
  analyzed_at?: string;
};

const clamp10 = (x: number) => Math.max(0, Math.min(10, x));

export function niveauPourScore(s: number): string {
  if (s >= 7) return "Fort";
  if (s >= 4) return "Moyen";
  if (s >= 1) return "Faible";
  return "Nul";
}

const RATIO_EXPLOITABLE: Record<string, number> = {
  plate: 0.7,
  inclinee: 0.55,
  inclinee_nord: 0.45,
  encombree: 0.4,
  inconnue: 0.6,
};
const M2_PAR_PLACE = 25;

export function scorerSolaire(
  surfaceExploitable: number | null,
  surfaceToiture: number | null,
  typeToiture: string | null,
): PotentielSolaire {
  const expl = surfaceExploitable ?? 0;
  let base: number;
  if (expl <= 0) base = 0;
  else if (expl >= 1500) base = 10;
  else if (expl >= 800) base = 7;
  else if (expl >= 300) base = 4;
  else base = 1;

  let bonus = 0;
  const t = (typeToiture ?? "").toLowerCase();
  if (base > 0) {
    if (t === "plate") bonus = 2;
    else if (t === "inclinee_nord" || t === "encombree") bonus = -2;
  }
  const score = clamp10(base + bonus);
  const just =
    base === 0
      ? "Pas de toiture exploitable détectée."
      : `~${Math.round(expl)} m² exploitables${t ? `, toiture ${t}` : ""}.`;
  return {
    score,
    niveau: niveauPourScore(score),
    surface_toiture_m2: surfaceToiture,
    surface_exploitable_m2: surfaceExploitable,
    type_toiture: typeToiture,
    justification: just,
  };
}

export function surfaceExploitableDepuis(
  surfaceToiture: number | null,
  type: string | null,
  ratioVision: number | null,
): number | null {
  if (!surfaceToiture || surfaceToiture <= 0) return null;
  let ratio = ratioVision;
  if (ratio == null || ratio <= 0 || ratio > 1) {
    ratio = RATIO_EXPLOITABLE[(type ?? "inconnue").toLowerCase()] ?? 0.6;
  }
  return Math.round(surfaceToiture * ratio * 10) / 10;
}

export function scorerOmbrieres(
  parkingPresent: boolean,
  nbPlaces: number | null,
  surfaceParking: number | null,
  partage: boolean | null,
  exploitant: string | null,
): PotentielOmbrieres {
  let places = nbPlaces ?? 0;
  if (!places && surfaceParking) places = Math.floor(surfaceParking / M2_PAR_PLACE);
  let base: number;
  if (!parkingPresent || places <= 0) base = 0;
  else if (places >= 150) base = 10;
  else if (places >= 60) base = 7;
  else if (places >= 20) base = 4;
  else base = 1;

  let bonus = 0;
  if (base > 0 && partage != null) bonus = partage ? -3 : 2;
  const score = clamp10(base + bonus);
  const just =
    base === 0
      ? "Pas de parking exploitable détecté."
      : `~${places} places, parking ${partage ? "partagé" : partage === false ? "dédié" : "usage indéterminé"}.`;
  return {
    score,
    niveau: niveauPourScore(score),
    surface_parking_m2: surfaceParking,
    nb_places: places || null,
    partage,
    exploitant_probable: exploitant,
    justification: just,
  };
}

export function scorerBornes(
  surSite: number,
  voisinage1km: number,
  rayon10km: number,
  signauxVe: boolean,
  types: string[],
): PotentielBornes {
  let adoption = 0;
  if (voisinage1km > 0 || signauxVe) adoption += 3;
  if (rayon10km >= 10) adoption += 3;
  else if (rayon10km >= 1) adoption += 2;
  adoption = Math.min(6, adoption);
  const manque = surSite === 0 ? 4 : 1;
  const score = clamp10(adoption + manque);

  let just = surSite > 0 ? `Déjà ${surSite} borne(s) sur site ; ` : "Aucune borne sur site ; ";
  if (voisinage1km > 0 || signauxVe) just += "zone qui s'électrifie (voisinage / signaux VE).";
  else if (rayon10km > 0) just += `${rayon10km} borne(s) dans un rayon de 10 km.`;
  else just += "peu d'infrastructure de recharge alentour.";
  return {
    score,
    niveau: niveauPourScore(score),
    sur_site: surSite,
    voisinage_1km: voisinage1km,
    rayon_10km: rayon10km,
    types,
    justification: just,
  };
}

// --- Emprise bâtie IGN (surface toiture précise via WFS BD TOPO) ---

const M_PAR_DEG_LAT = 110540;
const mParDegLon = (lat: number) => 111320 * Math.cos((lat * Math.PI) / 180);

function aireAnneauM2(anneau: number[][], lat0: number): number {
  const kx = mParDegLon(lat0);
  const ky = M_PAR_DEG_LAT;
  let s = 0;
  for (let i = 0; i < anneau.length - 1; i++) {
    const [lon1, lat1] = anneau[i];
    const [lon2, lat2] = anneau[i + 1];
    s += lon1 * kx * (lat2 * ky) - lon2 * kx * (lat1 * ky);
  }
  return Math.abs(s) / 2;
}

function pointDansAnneau(lat: number, lon: number, anneau: number[][]): boolean {
  let dedans = false;
  for (let i = 0, j = anneau.length - 1; i < anneau.length; j = i++) {
    const [loni, lati] = anneau[i];
    const [lonj, latj] = anneau[j];
    if (
      lati > lat !== latj > lat &&
      lon < ((lonj - loni) * (lat - lati)) / (latj - lati || 1e-12) + loni
    ) {
      dedans = !dedans;
    }
  }
  return dedans;
}

export async function surfaceBatieM2(lat: number, lon: number): Promise<number | null> {
  const dlat = 70 / M_PAR_DEG_LAT;
  const dlon = 70 / mParDegLon(lat);
  const bbox = `${lat - dlat},${lon - dlon},${lat + dlat},${lon + dlon},EPSG:4326`;
  const params = new URLSearchParams({
    SERVICE: "WFS",
    VERSION: "2.0.0",
    REQUEST: "GetFeature",
    TYPENAMES: "BDTOPO_V3:batiment",
    SRSNAME: "EPSG:4326",
    BBOX: bbox,
    OUTPUTFORMAT: "application/json",
    COUNT: "30",
  });
  try {
    const res = await fetch(`https://data.geopf.fr/wfs/ows?${params.toString()}`);
    if (!res.ok) return null;
    const gj = await res.json();
    const candidats: { dedans: boolean; aire: number }[] = [];
    for (const feat of gj.features ?? []) {
      const geom = feat.geometry ?? {};
      const polys: number[][][] =
        geom.type === "Polygon"
          ? [geom.coordinates?.[0]]
          : geom.type === "MultiPolygon"
            ? geom.coordinates.map((p: number[][][]) => p[0])
            : [];
      for (const anneau of polys) {
        if (!anneau || anneau.length < 4) continue;
        candidats.push({ dedans: pointDansAnneau(lat, lon, anneau), aire: aireAnneauM2(anneau, lat) });
      }
    }
    if (!candidats.length) return null;
    const contenants = candidats.filter((c) => c.dedans).map((c) => c.aire);
    const aire = contenants.length ? Math.max(...contenants) : Math.max(...candidats.map((c) => c.aire));
    return Math.round(aire * 10) / 10;
  } catch {
    return null;
  }
}

// --- Bornes IRVE via OpenChargeMap (optionnel, si clé) ---

const R_TERRE_KM = 6371;
export function haversineKm(la1: number, lo1: number, la2: number, lo2: number): number {
  const p1 = (la1 * Math.PI) / 180;
  const p2 = (la2 * Math.PI) / 180;
  const dphi = ((la2 - la1) * Math.PI) / 180;
  const dl = ((lo2 - lo1) * Math.PI) / 180;
  const a =
    Math.sin(dphi / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * R_TERRE_KM * Math.asin(Math.sqrt(a));
}

export type ComptageBornes = {
  sur_site: number;
  voisinage_1km: number;
  rayon_10km: number;
  types: string[];
};

export async function compterBornes(lat: number, lon: number): Promise<ComptageBornes> {
  const vide: ComptageBornes = { sur_site: 0, voisinage_1km: 0, rayon_10km: 0, types: [] };
  const key = process.env.OPENCHARGEMAP_API_KEY;
  if (!key) return vide;
  try {
    const url = new URL("https://api.openchargemap.io/v3/poi/");
    url.searchParams.set("latitude", String(lat));
    url.searchParams.set("longitude", String(lon));
    url.searchParams.set("distance", "10");
    url.searchParams.set("distanceunit", "KM");
    url.searchParams.set("maxresults", "200");
    url.searchParams.set("key", key);
    const res = await fetch(url.toString());
    if (!res.ok) return vide;
    const pois = (await res.json()) as Array<{
      AddressInfo?: { Latitude?: number; Longitude?: number };
      Connections?: Array<{ PowerKW?: number }>;
    }>;
    const c: ComptageBornes = { sur_site: 0, voisinage_1km: 0, rayon_10km: 0, types: [] };
    const types = new Set<string>();
    for (const poi of pois) {
      const blat = poi.AddressInfo?.Latitude;
      const blon = poi.AddressInfo?.Longitude;
      if (blat == null || blon == null) continue;
      const d = haversineKm(lat, lon, blat, blon);
      if (d <= 10) {
        c.rayon_10km += 1;
        const kw = poi.Connections?.[0]?.PowerKW;
        if (kw) types.add(kw >= 50 ? `rapide ${Math.round(kw)} kW (DC)` : `${Math.round(kw)} kW`);
      }
      if (d <= 1) c.voisinage_1km += 1;
      if (d <= 0.15) c.sur_site += 1;
    }
    c.types = [...types].slice(0, 4);
    return c;
  } catch {
    return vide;
  }
}

export function assembler(
  solaire: PotentielSolaire,
  ombrieres: PotentielOmbrieres,
  bornes: PotentielBornes,
  imageUrl: string,
): AnalysePotentiels {
  const scores: Record<string, number> = {
    solaire: solaire.score,
    ombrieres: ombrieres.score,
    bornes: bornes.score,
  };
  const meilleur = (Object.keys(scores) as Array<keyof typeof scores>).reduce((a, b) =>
    scores[a] >= scores[b] ? a : b,
  ) as "solaire" | "ombrieres" | "bornes";
  const libelle = {
    solaire: "solaire (toiture)",
    ombrieres: "ombrières (parking)",
    bornes: "bornes de recharge",
  }[meilleur];
  return {
    version: 2,
    solaire,
    ombrieres,
    bornes,
    meilleur,
    synthese: `Meilleur potentiel : ${libelle} (${scores[meilleur]}/10).`,
    image_url: imageUrl,
    analyzed_at: new Date().toISOString(),
  };
}
