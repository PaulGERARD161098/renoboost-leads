// Test d'intégration léger (« E2E » des helpers purs) : un seul jeu de données
// réaliste traverse les briques agent-first — stats par angle, angle gagnant par
// cible, carte des tournées, opportunités groupées, file d'appels du jour — et on
// vérifie qu'elles racontent une histoire COHÉRENTE entre elles. C'est le filet
// qui attrape une régression de composition qu'un test unitaire isolé manquerait.

import { describe, it, expect } from "vitest";
import { statsParAngle, angleGagnantParCible, type LeadStatCible } from "@/lib/stats-angles";
import { pointsTournee, opportunitesAutourDesRdv, type LeadCarto } from "@/lib/tournees";
import { fileAppelsDuJour, type LeadAppel } from "@/lib/appels-du-jour";
import type { LeadStatus } from "@/lib/database.types";

type DemoLead = {
  id: string;
  entreprise: string;
  ville: string;
  verticale: string;
  statut: LeadStatus;
  angle: "solaire" | "ombrieres" | "bornes" | null;
  score: number;
  lat: number;
  lng: number;
  tel: string | null;
  sentDays?: number;
  repliedDays?: number;
  rdvInDays?: number;
  relanceInDays?: number;
};

const NOW = new Date("2026-06-12T08:00:00Z");
const at = (days: number) =>
  new Date(NOW.getTime() + days * 86_400_000).toISOString();

// Jeu de démo aligné sur web/supabase/seed_demo.sql (Hauts-de-France).
const DEMO: DemoLead[] = [
  // Cible « rossini » — bornes domine (4 envois, 3 réponses) vs ombrières (2, 0).
  { id: "l1", entreprise: "Transports Delahaye", ville: "Lille", verticale: "rossini", statut: "rdv_pris", angle: "bornes", score: 88, lat: 50.6292, lng: 3.0573, tel: "0320001122", sentDays: -12, repliedDays: -9, rdvInDays: 4 },
  { id: "l2", entreprise: "Logipole Nord", ville: "Roubaix", verticale: "rossini", statut: "repondu", angle: "bornes", score: 82, lat: 50.6942, lng: 3.1746, tel: "0320334455", sentDays: -8, repliedDays: -3 },
  { id: "l3", entreprise: "Garage Central", ville: "Tourcoing", verticale: "rossini", statut: "repondu", angle: "bornes", score: 76, lat: 50.7236, lng: 3.1610, tel: "0320556677", sentDays: -6, repliedDays: -2 },
  { id: "l4", entreprise: "Distri-Frais", ville: "Villeneuve-d'Ascq", verticale: "rossini", statut: "envoye", angle: "bornes", score: 79, lat: 50.62, lng: 3.143, tel: "0320667788", sentDays: -4 },
  { id: "l5", entreprise: "Super Vauban", ville: "Lens", verticale: "rossini", statut: "envoye", angle: "ombrieres", score: 71, lat: 50.4319, lng: 2.8323, tel: "0321112233", sentDays: -5, relanceInDays: 2 },
  { id: "l6", entreprise: "Jardinerie Bassin", ville: "Douai", verticale: "rossini", statut: "a_relancer", angle: "ombrieres", score: 64, lat: 50.3714, lng: 3.08, tel: "0327223344", sentDays: -7, relanceInDays: 0 },
  // Cible « solaire » — solaire domine (50 %).
  { id: "l7", entreprise: "Menuiserie Lefebvre", ville: "Valenciennes", verticale: "solaire", statut: "gagne", angle: "solaire", score: 90, lat: 50.359, lng: 3.5236, tel: "0327334455", sentDays: -20, repliedDays: -15 },
  { id: "l8", entreprise: "Plasturgie Arras", ville: "Arras", verticale: "solaire", statut: "repondu", angle: "solaire", score: 84, lat: 50.291, lng: 2.7775, tel: "0321445566", sentDays: -9, repliedDays: -2 },
  { id: "l9", entreprise: "Imprimerie Béthune", ville: "Béthune", verticale: "solaire", statut: "ouvert", angle: "solaire", score: 73, lat: 50.53, lng: 2.64, tel: "0321556677", sentDays: -3 },
  { id: "l10", entreprise: "Brasserie Flandres", ville: "Dunkerque", verticale: "solaire", statut: "envoye", angle: "solaire", score: 80, lat: 51.0344, lng: 2.3768, tel: "0328667788", sentDays: -4 },
];

const toCible = (d: DemoLead): LeadStatCible => ({
  verticale_id: d.verticale,
  statut: d.statut,
  mail_angle: d.angle,
  sent_at: d.sentDays != null ? at(d.sentDays) : null,
  replied_at: d.repliedDays != null ? at(d.repliedDays) : null,
});

const toCarto = (d: DemoLead): LeadCarto => ({
  id: d.id,
  entreprise: d.entreprise,
  ville: d.ville,
  statut: d.statut,
  score: d.score,
  latitude: d.lat,
  longitude: d.lng,
  rdv_at: d.rdvInDays != null ? at(d.rdvInDays) : null,
  contact_tel: d.tel,
});

const toAppel = (d: DemoLead): LeadAppel => ({
  id: d.id,
  entreprise: d.entreprise,
  ville: d.ville,
  statut: d.statut,
  score: d.score,
  contact_nom: null,
  contact_tel: d.tel,
  relance_at: d.relanceInDays != null ? at(d.relanceInDays) : null,
  call_statut: null,
  score_raison: `${d.entreprise} — terrain favorable`,
  vision_satellite: null,
});

describe("pipeline démo agent-first (intégration des helpers purs)", () => {
  it("angle gagnant par cible : bornes pour Rossini, solaire pour solaire", () => {
    const recos = angleGagnantParCible(DEMO.map(toCible));
    const byCible = new Map(recos.map((r) => [r.verticaleId, r]));
    expect(byCible.get("rossini")).toMatchObject({ angle: "bornes", tauxReponse: 75 });
    expect(byCible.get("solaire")).toMatchObject({ angle: "solaire", tauxReponse: 50 });
    // L'angle recommandé coïncide bien avec le meilleur de la table globale Rossini.
    const rossiniGlobal = statsParAngle(
      DEMO.filter((d) => d.verticale === "rossini").map(toCible),
    );
    expect(rossiniGlobal[0].angle).toBe("bornes");
  });

  it("carte des tournées : RDV en tête, conclus exclus, coords valides seulement", () => {
    const pts = pointsTournee(DEMO.map(toCarto));
    // Le gagné (l7) sort de la carte ; le RDV (l1) est en première position.
    expect(pts.some((p) => p.lead.id === "l7")).toBe(false);
    expect(pts[0].categorie).toBe("rdv");
    expect(pts[0].lead.id).toBe("l1");
  });

  it("opportunités groupées : le RDV de Lille fédère des prospects proches", () => {
    const opps = opportunitesAutourDesRdv(pointsTournee(DEMO.map(toCarto)));
    expect(opps.length).toBeGreaterThan(0);
    // Le RDV Delahaye (Lille) a des prospects chauds dans la métropole lilloise.
    const lille = opps.find((o) => o.rdv.lead.id === "l1");
    expect(lille).toBeTruthy();
    expect(lille!.aProximite.length).toBeGreaterThan(0);
  });

  it("file d'appels du jour : réponses chaudes prioritaires, RDV exclus", () => {
    const file = fileAppelsDuJour(DEMO.map(toAppel), NOW);
    expect(file.length).toBeGreaterThan(0);
    // Les leads « repondu » (priorité 1) passent avant les relances dues (priorité 3).
    expect(file[0].priorite).toBe(1);
    // Le RDV pris (l1) ne doit pas être rappelé à froid.
    expect(file.some((a) => a.lead.id === "l1")).toBe(false);
  });
});
