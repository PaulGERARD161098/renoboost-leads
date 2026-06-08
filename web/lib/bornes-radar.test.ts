import { describe, it, expect } from "vitest";
import {
  croiserRadarPotentiel,
  departementDeCodePostal,
  tallyLeadsParDepartement,
} from "@/lib/bornes-radar";

describe("departementDeCodePostal", () => {
  it("prend les deux premiers chiffres en métropole", () => {
    expect(departementDeCodePostal("69003")).toBe("69");
    expect(departementDeCodePostal("75012")).toBe("75");
  });

  it("pad un code postal tronqué de son zéro initial", () => {
    expect(departementDeCodePostal("1000")).toBe("01"); // Ain
  });

  it("gère la Corse via le seuil 20200", () => {
    expect(departementDeCodePostal("20000")).toBe("2A"); // Ajaccio
    expect(departementDeCodePostal("20200")).toBe("2B"); // Bastia
  });

  it("gère l'outre-mer sur trois chiffres", () => {
    expect(departementDeCodePostal("97400")).toBe("974"); // La Réunion
  });

  it("renvoie null sur entrée vide ou non numérique", () => {
    expect(departementDeCodePostal(null)).toBeNull();
    expect(departementDeCodePostal("")).toBeNull();
    expect(departementDeCodePostal("abc")).toBeNull();
  });
});

describe("tallyLeadsParDepartement", () => {
  it("compte par département et ignore les codes invalides", () => {
    const t = tallyLeadsParDepartement(["69003", "69100", "75001", null, "xx"]);
    expect(t).toEqual({ "69": 2, "75": 1 });
  });
});

describe("croiserRadarPotentiel", () => {
  const lignes = [
    { departement: "01", nom: "Ain", pour100k: 5, n: 30 }, // sous-équipé
    { departement: "75", nom: "Paris", pour100k: 50, n: 1000 }, // bien équipé
    { departement: "69", nom: "Rhône", pour100k: 8, n: 150 }, // sous-équipé
  ];

  it("remonte les priorités (sous-équipé ET pipeline) en tête", () => {
    const res = croiserRadarPotentiel(lignes, { "01": 3, "75": 10 });
    // 01 est sous-équipé ET a du pipeline → priorité, en tête.
    expect(res[0].departement).toBe("01");
    expect(res[0].priorite).toBe(true);
    // 75 a du pipeline mais n'est pas sous-équipé → pas priorité.
    expect(res.find((l) => l.departement === "75")?.priorite).toBe(false);
  });

  it("trie les priorités par pipeline décroissant", () => {
    const res = croiserRadarPotentiel(lignes, { "01": 2, "69": 9 });
    expect(res.map((l) => l.departement).slice(0, 2)).toEqual(["69", "01"]);
  });

  it("retombe sur le tri par sous-équipement sans pipeline", () => {
    const res = croiserRadarPotentiel(lignes, {});
    expect(res[0].departement).toBe("01"); // le plus sous-équipé
    expect(res.every((l) => l.priorite === false)).toBe(true);
  });

  it("renvoie [] sur liste vide", () => {
    expect(croiserRadarPotentiel([], { "01": 5 })).toEqual([]);
  });
});
