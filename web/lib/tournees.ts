// Carte des tournées — transformer les trous d'agenda en visites. Sélectionne
// les leads qui valent un déplacement (RDV à honorer, prospects chauds) et qui
// ont des coordonnées, en les catégorisant pour la carte. Helper pur, testé.

import type { LeadStatus } from "@/lib/database.types";

export type LeadCarto = {
  id: string;
  entreprise: string;
  ville: string | null;
  statut: LeadStatus;
  score: number | null;
  latitude: number | null;
  longitude: number | null;
  rdv_at: string | null;
  contact_tel: string | null;
};

export type CategorieTournee = "rdv" | "chaud" | "tiede";

export type PointTournee = {
  lead: LeadCarto;
  categorie: CategorieTournee;
  lat: number;
  lng: number;
};

export const CATEGORIE_META: Record<
  CategorieTournee,
  { label: string; color: string; emoji: string }
> = {
  rdv: { label: "RDV à honorer", color: "#0d9488", emoji: "📅" },
  chaud: { label: "Prospect chaud", color: "#dc2626", emoji: "🔥" },
  tiede: { label: "À relancer sur place", color: "#f59e0b", emoji: "🟠" },
};

/** Latitude/longitude plausibles pour la France métropolitaine (filtre les 0,0 et bruits). */
function coordsValides(
  lat: number | null,
  lng: number | null,
): { lat: number; lng: number } | null {
  if (lat == null || lng == null) return null;
  if (lat < 41 || lat > 52 || lng < -5.5 || lng > 10) return null;
  return { lat, lng };
}

/**
 * Catégorise un lead pour la tournée, ou null s'il n'a rien à y faire :
 *  • rdv   — RDV pris (à honorer sur le terrain) ;
 *  • chaud — a répondu, ou top lead (≥75) encore à contacter ;
 *  • tiède — à relancer.
 * Les conclus (gagné/perdu) et écartés sortent.
 */
export function categoriser(lead: LeadCarto): CategorieTournee | null {
  if ((["gagne", "perdu", "ecarte"] as LeadStatus[]).includes(lead.statut)) return null;
  if (lead.statut === "rdv_pris") return "rdv";
  if (lead.statut === "repondu") return "chaud";
  if (
    (["nouveau", "a_valider", "valide"] as LeadStatus[]).includes(lead.statut) &&
    (lead.score ?? 0) >= 75
  )
    return "chaud";
  if (lead.statut === "a_relancer") return "tiede";
  return null;
}

export function pointsTournee(leads: LeadCarto[]): PointTournee[] {
  const pts: PointTournee[] = [];
  for (const lead of leads) {
    const coords = coordsValides(lead.latitude, lead.longitude);
    if (!coords) continue;
    const categorie = categoriser(lead);
    if (!categorie) continue;
    pts.push({ lead, categorie, lat: coords.lat, lng: coords.lng });
  }
  // RDV d'abord, puis chauds, puis tièdes ; score décroissant à l'intérieur.
  const ordre: Record<CategorieTournee, number> = { rdv: 0, chaud: 1, tiede: 2 };
  pts.sort(
    (a, b) =>
      ordre[a.categorie] - ordre[b.categorie] ||
      (b.lead.score ?? 0) - (a.lead.score ?? 0),
  );
  return pts;
}

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

/**
 * Autour de chaque RDV, compte les prospects (chauds/tièdes) dans le rayon
 * donné : « ce jour-là, profite d'être dans le coin ». Renvoie les RDV qui ont
 * au moins un prospect à proximité, le plus fourni d'abord.
 */
export type OpportuniteTournee = {
  rdv: PointTournee;
  aProximite: PointTournee[];
};

export function opportunitesAutourDesRdv(
  points: PointTournee[],
  rayonKm = 20,
): OpportuniteTournee[] {
  const rdvs = points.filter((p) => p.categorie === "rdv");
  const prospects = points.filter((p) => p.categorie !== "rdv");
  const res: OpportuniteTournee[] = [];
  for (const rdv of rdvs) {
    const aProximite = prospects
      .filter((p) => haversineKm(rdv.lat, rdv.lng, p.lat, p.lng) <= rayonKm)
      .sort((a, b) => (b.lead.score ?? 0) - (a.lead.score ?? 0));
    if (aProximite.length > 0) res.push({ rdv, aProximite });
  }
  res.sort((a, b) => b.aProximite.length - a.aProximite.length);
  return res;
}
