import { describe, it, expect } from "vitest";
import {
  niveauPourScore,
  scorerSolaire,
  scorerOmbrieres,
  scorerBornes,
  surfaceExploitableDepuis,
  assembler,
} from "@/lib/potentiel";

describe("niveauPourScore", () => {
  it("mappe les seuils Fort/Moyen/Faible/Nul", () => {
    expect(niveauPourScore(0)).toBe("Nul");
    expect(niveauPourScore(1)).toBe("Faible");
    expect(niveauPourScore(4)).toBe("Moyen");
    expect(niveauPourScore(7)).toBe("Fort");
    expect(niveauPourScore(10)).toBe("Fort");
  });
});

describe("surfaceExploitableDepuis", () => {
  it("renvoie null sans toiture", () => {
    expect(surfaceExploitableDepuis(null, "plate", null)).toBeNull();
    expect(surfaceExploitableDepuis(0, "plate", null)).toBeNull();
  });
  it("applique le ratio vision quand valide (0,1]", () => {
    expect(surfaceExploitableDepuis(1000, "plate", 0.5)).toBe(500);
  });
  it("retombe sur le ratio par type quand la vision est hors borne", () => {
    expect(surfaceExploitableDepuis(1000, "plate", null)).toBe(700); // 0.7
    expect(surfaceExploitableDepuis(1000, "encombree", 2)).toBe(400); // 0.4
    expect(surfaceExploitableDepuis(1000, "inconnu", 0)).toBe(600); // défaut 0.6
  });
});

describe("scorerSolaire", () => {
  it("note 0 sans surface exploitable", () => {
    const s = scorerSolaire(0, null, null);
    expect(s.score).toBe(0);
    expect(s.niveau).toBe("Nul");
    expect(s.justification).toMatch(/Pas de toiture/);
  });
  it("grande toiture plate = bonus +2 plafonné à 10", () => {
    expect(scorerSolaire(1500, 2000, "plate").score).toBe(10);
  });
  it("toiture nord pénalisée", () => {
    // base 7 (≥800) - 2 = 5
    expect(scorerSolaire(800, 1000, "inclinee_nord").score).toBe(5);
  });
});

describe("scorerOmbrieres", () => {
  it("note 0 sans parking", () => {
    expect(scorerOmbrieres(false, null, null, null, null).score).toBe(0);
  });
  it("déduit les places depuis la surface (25 m²/place)", () => {
    // 500 m² -> 20 places -> base 4
    const s = scorerOmbrieres(true, null, 500, null, null);
    expect(s.nb_places).toBe(20);
    expect(s.score).toBe(4);
  });
  it("parking partagé pénalise, parking dédié bonifie", () => {
    expect(scorerOmbrieres(true, 60, null, true, null).score).toBe(4); // 7-3
    expect(scorerOmbrieres(true, 60, null, false, null).score).toBe(9); // 7+2
  });
});

describe("scorerBornes", () => {
  it("aucune infra : manque fort mais adoption nulle", () => {
    const b = scorerBornes(0, 0, 0, false, []);
    expect(b.score).toBe(4); // manque 4
    expect(b.justification).toMatch(/peu d'infrastructure/);
  });
  it("un signal VE active le bonus d'adoption même sans voisinage", () => {
    const sans = scorerBornes(0, 0, 0, false, []);
    const avec = scorerBornes(0, 0, 0, true, []);
    expect(avec.score).toBeGreaterThan(sans.score);
    expect(avec.justification).toMatch(/s'électrifie/);
  });
  it("borne déjà sur site réduit le manque", () => {
    const b = scorerBornes(2, 5, 12, false, ["AC"]);
    // adoption: voisinage>0 (+3) + rayon>=10 (+3) plafonné 6 ; manque 1 -> 7
    expect(b.score).toBe(7);
    expect(b.sur_site).toBe(2);
  });
});

describe("assembler", () => {
  it("désigne le meilleur potentiel et compose la synthèse", () => {
    const solaire = scorerSolaire(1500, 2000, "plate"); // 10
    const ombrieres = scorerOmbrieres(true, 20, null, null, null); // 4
    const bornes = scorerBornes(0, 0, 0, false, []); // 4
    const a = assembler(solaire, ombrieres, bornes, "http://img");
    expect(a.version).toBe(2);
    expect(a.meilleur).toBe("solaire");
    expect(a.synthese).toMatch(/solaire \(toiture\) \(10\/10\)/);
    expect(a.image_url).toBe("http://img");
  });
});
