import type { SupabaseClient } from "@supabase/supabase-js";

// Requêtes géo sur les bornes de recharge consolidées (table bornes_recharge).
// Distances par bounding-box (lat/lng indexés) + haversine — pas de PostGIS.

const R_TERRE_KM = 6371;

export function haversineKm(
  aLat: number,
  aLng: number,
  bLat: number,
  bLng: number,
): number {
  const dLat = ((bLat - aLat) * Math.PI) / 180;
  const dLng = ((bLng - aLng) * Math.PI) / 180;
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((aLat * Math.PI) / 180) *
      Math.cos((bLat * Math.PI) / 180) *
      Math.sin(dLng / 2) ** 2;
  return 2 * R_TERRE_KM * Math.asin(Math.sqrt(s));
}

export type ProximiteBornes = {
  sur_site: number; // < 150 m : le prospect est probablement déjà équipé
  voisinage: number; // < 500 m : un voisin immédiat est équipé
  rayon: number; // dans le rayon demandé
  rayon_km: number;
  dont_rossini: number; // bornes posées par Rossini Energy dans le rayon
  plus_proche_km: number | null;
  operateurs: { nom: string; n: number }[]; // top opérateurs dans le rayon
};

type Ligne = { lat: number; lng: number; source: string; operateur: string | null };

/** Bornes autour d'un point (bbox + haversine). lat/lng en degrés décimaux. */
export async function bornesProximite(
  supabase: SupabaseClient,
  lat: number,
  lng: number,
  rayonKm = 10,
): Promise<ProximiteBornes> {
  const dLat = rayonKm / 111;
  const dLng = rayonKm / (111 * Math.max(0.1, Math.cos((lat * Math.PI) / 180)));
  const { data } = await supabase
    .from("bornes_recharge")
    .select("lat, lng, source, operateur")
    .gte("lat", lat - dLat)
    .lte("lat", lat + dLat)
    .gte("lng", lng - dLng)
    .lte("lng", lng + dLng)
    .not("lat", "is", null)
    .not("lng", "is", null)
    .limit(3000);

  const res: ProximiteBornes = {
    sur_site: 0,
    voisinage: 0,
    rayon: 0,
    rayon_km: rayonKm,
    dont_rossini: 0,
    plus_proche_km: null,
    operateurs: [],
  };
  const opTally = new Map<string, number>();
  for (const b of (data as Ligne[] | null) ?? []) {
    const d = haversineKm(lat, lng, b.lat, b.lng);
    if (d > rayonKm) continue;
    res.rayon += 1;
    if (d < 0.15) res.sur_site += 1;
    if (d < 0.5) res.voisinage += 1;
    if (b.source === "rossini") res.dont_rossini += 1;
    if (res.plus_proche_km === null || d < res.plus_proche_km) res.plus_proche_km = d;
    if (b.operateur) opTally.set(b.operateur, (opTally.get(b.operateur) ?? 0) + 1);
  }
  res.operateurs = [...opTally.entries()]
    .map(([nom, n]) => ({ nom, n }))
    .sort((a, b) => b.n - a.n)
    .slice(0, 5);
  if (res.plus_proche_km !== null) res.plus_proche_km = Math.round(res.plus_proche_km * 100) / 100;
  return res;
}

export type StatsDepartement = {
  departement: string;
  total: number;
  par_source: Record<string, number>;
  top_operateurs: { nom: string; n: number }[];
};

/** Compte les bornes d'un département + répartition par source et opérateurs. */
export async function bornesParDepartement(
  supabase: SupabaseClient,
  departement: string,
): Promise<StatsDepartement> {
  const { count: total } = await supabase
    .from("bornes_recharge")
    .select("*", { count: "exact", head: true })
    .eq("departement", departement);

  const parSource: Record<string, number> = {};
  for (const s of ["irve", "rossini", "chargemap"]) {
    const { count } = await supabase
      .from("bornes_recharge")
      .select("*", { count: "exact", head: true })
      .eq("departement", departement)
      .eq("source", s);
    if (count) parSource[s] = count;
  }

  const { data } = await supabase
    .from("bornes_recharge")
    .select("operateur")
    .eq("departement", departement)
    .not("operateur", "is", null)
    .limit(8000);
  const opTally = new Map<string, number>();
  for (const r of (data as { operateur: string | null }[] | null) ?? []) {
    if (r.operateur) opTally.set(r.operateur, (opTally.get(r.operateur) ?? 0) + 1);
  }
  const top = [...opTally.entries()]
    .map(([nom, n]) => ({ nom, n }))
    .sort((a, b) => b.n - a.n)
    .slice(0, 8);

  return {
    departement,
    total: total ?? 0,
    par_source: parSource,
    top_operateurs: top,
  };
}
