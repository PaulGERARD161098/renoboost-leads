import { describe, it, expect } from "vitest";
import { anglePhrase, fileAppelsDuJour, type LeadAppel } from "@/lib/appels-du-jour";

const base: Omit<LeadAppel, "id" | "entreprise" | "statut"> = {
  ville: null,
  score: 80,
  contact_nom: null,
  contact_tel: null,
  relance_at: null,
  call_statut: null,
  score_raison: null,
  vision_satellite: null,
};

const lead = (
  id: string,
  statut: LeadAppel["statut"],
  extra: Partial<LeadAppel> = {},
): LeadAppel => ({ ...base, id, entreprise: id, statut, ...extra });

const now = new Date("2026-06-11T08:00:00Z");

describe("fileAppelsDuJour — priorisation", () => {
  it("ordonne : répondu > bascule téléphone > relance due > top lead frais", () => {
    const file = fileAppelsDuJour(
      [
        lead("top", "valide", { score: 90 }),
        lead("relance", "a_relancer", { relance_at: "2026-06-10T10:00:00Z" }),
        lead("tel", "envoye", { call_statut: "a_appeler" }),
        lead("chaud", "repondu"),
      ],
      now,
    );
    expect(file.map((a) => a.lead.id)).toEqual(["chaud", "tel", "relance", "top"]);
  });

  it("ignore les écartés/conclus/RDV pris et les relances futures", () => {
    const file = fileAppelsDuJour(
      [
        lead("gagne", "gagne"),
        lead("rdv", "rdv_pris"),
        lead("plus-tard", "envoye", { relance_at: "2026-06-20T10:00:00Z" }),
        lead("tiede", "valide", { score: 60 }),
      ],
      now,
    );
    expect(file).toHaveLength(0);
  });

  it("départage une même priorité par score décroissant et plafonne à max", () => {
    const file = fileAppelsDuJour(
      [
        lead("b", "valide", { score: 80 }),
        lead("a", "valide", { score: 95 }),
        lead("c", "valide", { score: 78 }),
      ],
      now,
      2,
    );
    expect(file.map((a) => a.lead.id)).toEqual(["a", "b"]);
  });
});

describe("anglePhrase", () => {
  it("préfère le meilleur potentiel v2", () => {
    const phrase = anglePhrase({
      vision_satellite: { version: 2, bornes: { score: 9 }, meilleur: "bornes" },
      score_raison: "vieux texte",
    });
    expect(phrase).toBe("bornes VE (9/10)");
  });

  it("retombe sur le score_raison tronqué, ou null", () => {
    const long = anglePhrase({ vision_satellite: null, score_raison: "x".repeat(120) });
    expect(long?.endsWith("…")).toBe(true);
    expect(long!.length).toBeLessThanOrEqual(90);
    expect(anglePhrase({ vision_satellite: null, score_raison: null })).toBeNull();
  });
});
