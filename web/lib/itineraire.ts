// Planificateur d'itinéraire de tournée (charte agent-first : on ne se contente
// pas d'AFFICHER les points sur la carte, on PROPOSE l'ordre des visites).
//
// Heuristique : plus proche voisin (départ fixé) puis amélioration 2-opt sur le
// chemin ouvert (on ne revient pas au point de départ) — assez pour un ordre de
// visites lisible et court, sans dépendre d'un service de routage externe. Les
// distances sont à vol d'oiseau (haversine) : un ordre, pas un GPS au mètre.

import { haversineKm, type PointTournee } from "@/lib/tournees";

export type Geo = { lat: number; lng: number };

export type EtapeItineraire = {
  point: PointTournee;
  ordre: number; // 1-based
  legKm: number; // distance depuis l'étape précédente (ou le départ)
  cumulKm: number; // distance cumulée depuis le départ
  etaMin: number; // minutes après le départ avant d'arriver à cette étape
  retardRdv: boolean; // RDV horodaté dont l'arrivée estimée tombe APRÈS l'heure du RDV
};

export type Itineraire = {
  // Point de départ : « ma position » fournie, sinon la 1ʳᵉ visite (ancre du jour).
  depart: { lat: number; lng: number; label: string };
  etapes: EtapeItineraire[];
  distanceTotaleKm: number;
  dureeRouteMin: number; // estimation grossière (vitesse moyenne ~50 km/h)
};

// Fenêtres horaires : heure de départ (pour les ETA) + temps passé par visite.
export type OptsItineraire = { departISO?: string | null; dwellMin?: number };

const VITESSE_MOY_KMH = 50;
const DWELL_DEFAUT_MIN = 30;

/** Ordre des points par plus proche voisin depuis `start` (indices dans `pts`). */
function plusProcheVoisin(pts: Geo[], startIdx: number): number[] {
  const n = pts.length;
  const vus = new Array<boolean>(n).fill(false);
  const ordre = [startIdx];
  vus[startIdx] = true;
  let courant = startIdx;
  for (let k = 1; k < n; k++) {
    let best = -1;
    let bestD = Infinity;
    for (let j = 0; j < n; j++) {
      if (vus[j]) continue;
      const d = haversineKm(pts[courant].lat, pts[courant].lng, pts[j].lat, pts[j].lng);
      if (d < bestD) {
        bestD = d;
        best = j;
      }
    }
    vus[best] = true;
    ordre.push(best);
    courant = best;
  }
  return ordre;
}

/** Longueur d'un chemin ouvert (origine → suite des points dans l'ordre donné). */
function longueurChemin(origine: Geo | null, pts: Geo[], ordre: number[]): number {
  let total = 0;
  let prev = origine ?? pts[ordre[0]];
  const debut = origine ? 0 : 1;
  for (let i = debut; i < ordre.length; i++) {
    const p = pts[ordre[i]];
    total += haversineKm(prev.lat, prev.lng, p.lat, p.lng);
    prev = p;
  }
  return total;
}

/**
 * Amélioration 2-opt d'un chemin ouvert : tant qu'inverser un segment raccourcit
 * le trajet, on le fait. `figerPremier` garde la 1ʳᵉ étape en place (cas « départ
 * = première visite »). Déterministe.
 */
function deuxOpt(
  origine: Geo | null,
  pts: Geo[],
  ordreInit: number[],
  figerPremier: boolean,
): number[] {
  let ordre = ordreInit.slice();
  let meilleure = longueurChemin(origine, pts, ordre);
  let ameliore = true;
  const debut = figerPremier ? 1 : 0;
  while (ameliore) {
    ameliore = false;
    for (let i = debut; i < ordre.length - 1; i++) {
      for (let j = i + 1; j < ordre.length; j++) {
        const candidat = ordre.slice(0, i).concat(
          ordre.slice(i, j + 1).reverse(),
          ordre.slice(j + 1),
        );
        const d = longueurChemin(origine, pts, candidat);
        if (d + 1e-9 < meilleure) {
          ordre = candidat;
          meilleure = d;
          ameliore = true;
        }
      }
    }
  }
  return ordre;
}

/**
 * Planifie l'ordre des visites.
 *  • avec `origin` (ex. « ma position ») : tous les points sont des arrêts,
 *    départ = l'origine fournie ;
 *  • sans origin : on part de la 1ʳᵉ visite (les points arrivent déjà triés par
 *    priorité — RDV d'abord), qui devient l'étape 1.
 */
/**
 * Quand ≥2 RDV sont horodatés, la journée est structurée par les rendez-vous :
 * on les honore dans l'ordre CHRONOLOGIQUE (épine dorsale fixe) et on insère les
 * prospects libres au moindre détour (insertion la moins coûteuse). Renvoie null
 * s'il n'y a pas assez de RDV horodatés pour contraindre l'ordre.
 */
function ordreParHoraires(
  points: PointTournee[],
  pts: Geo[],
  origine: Geo | null,
): number[] | null {
  const horodates = points
    .map((p, i) => ({ i, t: p.categorie === "rdv" ? p.lead.rdv_at : null }))
    .filter((x): x is { i: number; t: string } => Boolean(x.t) && !Number.isNaN(Date.parse(x.t!)));
  if (horodates.length < 2) return null;

  const seq = horodates
    .sort((a, b) => Date.parse(a.t) - Date.parse(b.t))
    .map((x) => x.i);
  const libres = points.map((_, i) => i).filter((i) => !seq.includes(i));
  const km = (a: Geo, b: Geo) => haversineKm(a.lat, a.lng, b.lat, b.lng);

  for (const l of libres) {
    let bestPos = seq.length;
    let bestDelta = Infinity;
    // Sans origine, interdit d'insérer avant l'ancre (le 1er RDV reste le départ).
    for (let k = origine ? 0 : 1; k <= seq.length; k++) {
      const prev = k === 0 ? origine! : pts[seq[k - 1]];
      const next = k < seq.length ? pts[seq[k]] : null;
      const delta = next
        ? km(prev, pts[l]) + km(pts[l], next) - km(prev, next)
        : km(prev, pts[l]);
      if (delta < bestDelta) {
        bestDelta = delta;
        bestPos = k;
      }
    }
    seq.splice(bestPos, 0, l);
  }
  return seq;
}

export function planifierItineraire(
  points: PointTournee[],
  origin?: { lat: number; lng: number; label?: string } | null,
  opts: OptsItineraire = {},
): Itineraire {
  const vide: Itineraire = {
    depart: origin
      ? { lat: origin.lat, lng: origin.lng, label: origin.label ?? "Ma position" }
      : { lat: 0, lng: 0, label: "—" },
    etapes: [],
    distanceTotaleKm: 0,
    dureeRouteMin: 0,
  };
  if (points.length === 0) return vide;

  const pts: Geo[] = points.map((p) => ({ lat: p.lat, lng: p.lng }));
  const origine: Geo | null = origin ? { lat: origin.lat, lng: origin.lng } : null;

  // Priorité aux fenêtres horaires des RDV ; sinon ordre géométrique (NN + 2-opt).
  let ordre = ordreParHoraires(points, pts, origine);
  if (!ordre) {
    if (origine) {
      let proche = 0;
      let procheD = Infinity;
      for (let j = 0; j < pts.length; j++) {
        const d = haversineKm(origine.lat, origine.lng, pts[j].lat, pts[j].lng);
        if (d < procheD) {
          procheD = d;
          proche = j;
        }
      }
      ordre = deuxOpt(origine, pts, plusProcheVoisin(pts, proche), false);
    } else {
      ordre = deuxOpt(null, pts, plusProcheVoisin(pts, 0), true);
    }
  }

  const depart: Itineraire["depart"] = origin
    ? { lat: origin.lat, lng: origin.lng, label: origin.label ?? "Ma position" }
    : { lat: points[ordre[0]].lat, lng: points[ordre[0]].lng, label: points[ordre[0]].lead.entreprise };

  const dwell = opts.dwellMin ?? DWELL_DEFAUT_MIN;
  const departEpoch = opts.departISO ? Date.parse(opts.departISO) : NaN;
  const etapes: EtapeItineraire[] = [];
  let prev: Geo = origine ?? pts[ordre[0]];
  let cumul = 0;
  let cumulMin = 0;
  for (let i = 0; i < ordre.length; i++) {
    const idx = ordre[i];
    const p = pts[idx];
    const premierSansOrigine = !origine && i === 0;
    const leg = premierSansOrigine ? 0 : haversineKm(prev.lat, prev.lng, p.lat, p.lng);
    cumul += leg;
    cumulMin += (leg / VITESSE_MOY_KMH) * 60; // temps de route jusqu'à cette étape
    const etaMin = Math.round(cumulMin);
    let retardRdv = false;
    const rdvAt = points[idx].lead.rdv_at;
    if (!Number.isNaN(departEpoch) && points[idx].categorie === "rdv" && rdvAt) {
      const arrivee = departEpoch + etaMin * 60_000;
      retardRdv = !Number.isNaN(Date.parse(rdvAt)) && arrivee > Date.parse(rdvAt);
    }
    etapes.push({
      point: points[idx],
      ordre: i + 1,
      legKm: Math.round(leg * 10) / 10,
      cumulKm: Math.round(cumul * 10) / 10,
      etaMin,
      retardRdv,
    });
    cumulMin += dwell; // temps passé sur place avant de repartir
    prev = p;
  }

  const distanceTotaleKm = Math.round(cumul * 10) / 10;
  return {
    depart,
    etapes,
    distanceTotaleKm,
    dureeRouteMin: Math.round((distanceTotaleKm / VITESSE_MOY_KMH) * 60),
  };
}

/**
 * Lien Google Maps « directions » avec tous les arrêts (ouvre la navigation).
 * Google limite les waypoints d'une URL : au-delà de `maxArrets`, on tronque (les
 * premiers arrêts, les plus prioritaires/proches, sont conservés).
 */
export function lienGoogleMaps(it: Itineraire, maxArrets = 10): string | null {
  if (it.etapes.length === 0) return null;
  const coord = (g: { lat: number; lng: number }) => `${g.lat},${g.lng}`;
  const arrets = it.etapes.slice(0, maxArrets).map((e) => ({
    lat: e.point.lat,
    lng: e.point.lng,
  }));

  // Sans origine fournie, la 1ʳᵉ visite EST le départ → ne pas la dupliquer.
  const departEstUnArret = it.depart.label !== "Ma position";
  const origine = coord(it.depart);
  const sequence = departEstUnArret ? arrets.slice(1) : arrets;
  if (sequence.length === 0) {
    return `https://www.google.com/maps/dir/?api=1&destination=${origine}`;
  }
  const destination = coord(sequence[sequence.length - 1]);
  const waypoints = sequence.slice(0, -1).map(coord).join("|");
  const params = new URLSearchParams({ api: "1", origin: origine, destination });
  if (waypoints) params.set("waypoints", waypoints);
  params.set("travelmode", "driving");
  return `https://www.google.com/maps/dir/?${params.toString()}`;
}
