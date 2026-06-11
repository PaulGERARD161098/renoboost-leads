import { describe, expect, it } from "vitest";
import {
  angleOutreach,
  buildOutreachPrompt,
  choisirReference,
  solaireFromVision,
  type ReferenceChantier,
} from "./outreach";

// Cas réel (retour Henry #45cee641) : site avec bornes 10/10 mais solaire et
// ombrières à 0/10 — le mail ne doit JAMAIS être piloté par les axes à 0.
const visionBornesSeules = {
  version: 2,
  solaire: { score: 0, justification: "Pas de toiture exploitable détectée." },
  ombrieres: { score: 0, justification: "Pas de parking exploitable détecté." },
  bornes: { score: 10, justification: "Zone qui s'électrifie." },
  meilleur: "bornes",
};

const lead = {
  entreprise: "Nestlé Lactalis",
  ville: "Cuincy",
  secteur: "Industrie agroalimentaire",
  effectif: null,
  contact_nom: null,
  score_raison: "Potentiel parking exploitable en Hauts-de-France.",
  vision: visionBornesSeules as Record<string, unknown>,
};

describe("buildOutreachPrompt — cohérence mail ↔ analyse v2", () => {
  it("met le meilleur potentiel en priorité et interdit les axes faibles", () => {
    const p = buildOutreachPrompt("approche", lead, "Ombrières solaires", null);
    expect(p).toContain("Potentiel à mettre en avant en priorité : 🔌 Bornes de recharge VE (10/10)");
    expect(p).toContain("INTERDIT de mettre en avant");
    expect(p).toContain("🅿️ Ombrières (parking) (0/10)");
    expect(p).toContain("🔆 Solaire (toiture) (0/10)");
  });

  it("fait primer les potentiels sur l'angle d'accroche détecté", () => {
    const p = buildOutreachPrompt("approche", lead, null, null);
    expect(p).toContain("qui priment");
  });

  it("n'émet pas d'interdiction quand aucun axe n'est faible", () => {
    const vision = {
      version: 2,
      solaire: { score: 8 },
      ombrieres: { score: 7 },
      bornes: { score: 9 },
      meilleur: "bornes",
    };
    const p = buildOutreachPrompt("approche", { ...lead, vision }, null, null);
    expect(p).not.toContain("INTERDIT");
  });

  it("reste strictement comme avant sans analyse (pas de bloc potentiels)", () => {
    const p = buildOutreachPrompt("approche", { ...lead, vision: null }, null, null);
    expect(p).not.toContain("Potentiels du site détectés");
    expect(p).not.toContain("INTERDIT");
  });
});

describe("buildOutreachPrompt — téléphone dans la signature", () => {
  it("ajoute le téléphone quand il est renseigné", () => {
    const p = buildOutreachPrompt("approche", lead, null, null, "Rossini Energy", "03 20 00 00 00");
    expect(p).toContain("03 20 00 00 00");
    expect(p).toContain("L'équipe Rossini Energy");
  });

  it("ignore un téléphone vide ou absent", () => {
    expect(buildOutreachPrompt("approche", lead, null, null, null, "  ")).not.toContain(
      "numéro de téléphone",
    );
    expect(buildOutreachPrompt("relance", lead, null, null)).not.toContain("numéro de téléphone");
  });
});

describe("angleOutreach — transparence du pilotage", () => {
  it("renvoie l'axe pilote en v2", () => {
    expect(angleOutreach(visionBornesSeules as Record<string, unknown>)).toEqual({
      pilote: true,
      cle: "bornes",
      label: "🔌 Bornes de recharge VE",
      score: 10,
    });
  });

  it("renvoie non piloté sans analyse ou en v1", () => {
    expect(angleOutreach(null)).toEqual({ pilote: false });
    expect(angleOutreach({ toiture: { surface_estimee_m2: 800 } })).toEqual({ pilote: false });
  });
});

describe("solaireFromVision — rétro-compatibilité", () => {
  it("v2 sans surface ni parking exploitables → null (mail générique)", () => {
    expect(solaireFromVision(visionBornesSeules as Record<string, unknown>)).toBeNull();
  });
});

describe("choisirReference — preuve sociale géolocalisée", () => {
  const refs: ReferenceChantier[] = [
    { nom: "A", ville: "Lille", lat: 50.63, lng: 3.06, axe: "ombrieres", description: null },
    { nom: "B", ville: "Douai", lat: 50.37, lng: 3.08, axe: "ombrieres", description: "40 places" },
    { nom: "C", ville: "Arras", lat: 50.29, lng: 2.78, axe: "bornes", description: null },
  ];
  // Prospect à Cuincy (à côté de Douai).
  const lead = { latitude: 50.37, longitude: 3.05 };

  it("prend la plus proche sur le même axe", () => {
    const r = choisirReference(refs, lead, "ombrieres");
    expect(r?.nom).toBe("B");
    expect(r?.distance_km).toBeLessThan(10);
  });

  it("retombe sur les autres axes si aucun ne correspond", () => {
    const r = choisirReference(refs, lead, "solaire");
    expect(r?.nom).toBe("B"); // plus proche toutes refs confondues
  });

  it("sans coordonnées du lead : première du bon axe, sans distance", () => {
    const r = choisirReference(refs, {}, "bornes");
    expect(r?.nom).toBe("C");
    expect(r?.distance_km).toBeNull();
  });

  it("liste vide → null", () => {
    expect(choisirReference([], lead, "bornes")).toBeNull();
  });
});
