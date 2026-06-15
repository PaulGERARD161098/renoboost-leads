import { describe, it, expect } from "vitest";
import { planifierItineraire, lienGoogleMaps } from "@/lib/itineraire";
import type { PointTournee, CategorieTournee } from "@/lib/tournees";

// 4 points alignés du sud au nord (même longitude) pour un ordre déterministe.
const pt = (
  id: string,
  lat: number,
  categorie: CategorieTournee = "chaud",
  score = 80,
): PointTournee => ({
  categorie,
  lat,
  lng: 3.0,
  lead: {
    id,
    entreprise: `Lead ${id}`,
    ville: id.toUpperCase(),
    statut: categorie === "rdv" ? "rdv_pris" : "repondu",
    score,
    latitude: lat,
    longitude: 3.0,
    rdv_at: null,
    contact_tel: null,
  },
});

const A = pt("a", 50.0);
const B = pt("b", 50.1);
const C = pt("c", 50.2);
const D = pt("d", 50.3);

const ordreIds = (it: ReturnType<typeof planifierItineraire>) =>
  it.etapes.map((e) => e.point.lead.id);

describe("planifierItineraire", () => {
  it("sans origine : part de la 1ʳᵉ visite (ancre) et reconstruit la ligne", () => {
    // Entrée volontairement désordonnée, mais A reste l'ancre (RDV/priorité).
    const it = planifierItineraire([A, C, B, D]);
    expect(it.depart.label).toBe("Lead a");
    expect(ordreIds(it)).toEqual(["a", "b", "c", "d"]);
    expect(it.etapes[0].legKm).toBe(0); // l'ancre est le point de départ
    expect(it.etapes[0].ordre).toBe(1);
  });

  it("cumul croissant et total = cumul de la dernière étape", () => {
    const it = planifierItineraire([A, B, C, D]);
    const cumuls = it.etapes.map((e) => e.cumulKm);
    for (let i = 1; i < cumuls.length; i++) {
      expect(cumuls[i]).toBeGreaterThanOrEqual(cumuls[i - 1]);
    }
    expect(it.distanceTotaleKm).toBe(it.etapes.at(-1)!.cumulKm);
    expect(it.dureeRouteMin).toBeGreaterThan(0);
  });

  it("2-opt : dénoue un trajet croisé pour retrouver la ligne", () => {
    // A fixé en tête, mais D (le plus loin) placé tôt = ordre d'entrée croisé.
    const planifie = planifierItineraire([A, D, B, C]);
    expect(ordreIds(planifie)).toEqual(["a", "b", "c", "d"]);
  });

  it("avec origine au nord : visite du plus proche au plus loin", () => {
    const it = planifierItineraire([A, B, C, D], { lat: 50.35, lng: 3.0, label: "Base" });
    expect(it.depart.label).toBe("Base");
    expect(ordreIds(it)).toEqual(["d", "c", "b", "a"]);
    expect(it.etapes[0].legKm).toBeGreaterThan(0); // 1ʳᵉ étape distante de l'origine
  });

  it("jeu vide → itinéraire vide", () => {
    const it = planifierItineraire([]);
    expect(it.etapes).toEqual([]);
    expect(it.distanceTotaleKm).toBe(0);
  });
});

describe("planifierItineraire — fenêtres horaires (RDV)", () => {
  const rdv = (id: string, lat: number, rdvISO: string): PointTournee => ({
    categorie: "rdv",
    lat,
    lng: 3.0,
    lead: {
      id,
      entreprise: `RDV ${id}`,
      ville: id.toUpperCase(),
      statut: "rdv_pris",
      score: 80,
      latitude: lat,
      longitude: 3.0,
      rdv_at: rdvISO,
      contact_tel: null,
    },
  });

  // R1 (sud, 9h) et R2 (nord, 11h), un prospect libre L au milieu — entrée mélangée.
  const R1 = rdv("r1", 50.0, "2026-06-15T07:00:00Z");
  const R2 = rdv("r2", 50.3, "2026-06-15T07:10:00Z");
  const L = pt("l", 50.15);

  it("honore les RDV dans l'ordre chronologique, insère le libre au milieu", () => {
    const it = planifierItineraire([R2, L, R1]);
    expect(it.etapes.map((e) => e.point.lead.id)).toEqual(["r1", "l", "r2"]);
    expect(it.depart.label).toBe("RDV r1"); // l'ancre est le 1er RDV
  });

  it("calcule l'ETA et signale le risque de retard sur un RDV trop tôt", () => {
    const it = planifierItineraire([R2, L, R1], null, {
      departISO: "2026-06-15T07:00:00Z",
      dwellMin: 30,
    });
    const eR1 = it.etapes.find((e) => e.point.lead.id === "r1")!;
    const eR2 = it.etapes.find((e) => e.point.lead.id === "r2")!;
    expect(eR1.etaMin).toBe(0);
    expect(eR1.retardRdv).toBe(false); // arrivée 07:00 = heure du RDV
    expect(eR2.etaMin).toBeGreaterThan(eR1.etaMin);
    expect(eR2.retardRdv).toBe(true); // RDV à 07:10 mais arrivée bien plus tard
  });

  it("sans heure de départ : pas de calcul de retard", () => {
    const it = planifierItineraire([R1, R2]);
    expect(it.etapes.every((e) => e.retardRdv === false)).toBe(true);
  });
});

describe("lienGoogleMaps", () => {
  it("sans origine : la 1ʳᵉ visite est l'origine, pas un waypoint dupliqué", () => {
    const it = planifierItineraire([A, B, C, D]);
    const url = decodeURIComponent(lienGoogleMaps(it)!);
    expect(url).toContain("origin=50,3");
    expect(url).toContain("destination=50.3,3");
    expect(url).toContain("waypoints=50.1,3|50.2,3"); // b puis c
    expect(url).toContain("travelmode=driving");
  });

  it("avec origine : l'origine est le départ, toutes les visites suivent", () => {
    const it = planifierItineraire([A, B, C, D], { lat: 50.35, lng: 3.0, label: "Base" });
    const url = decodeURIComponent(lienGoogleMaps(it)!);
    expect(url).toContain("origin=50.35,3");
    expect(url).toContain("destination=50,3"); // a, le plus loin, en dernier
  });

  it("jeu vide → pas de lien", () => {
    expect(lienGoogleMaps(planifierItineraire([]))).toBeNull();
  });
});
