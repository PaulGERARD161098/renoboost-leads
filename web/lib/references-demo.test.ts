import { describe, it, expect } from "vitest";
import { REFERENCES_EXEMPLES } from "@/lib/references-demo";

describe("REFERENCES_EXEMPLES", () => {
  it("couvre les trois axes avec des champs complets", () => {
    expect(REFERENCES_EXEMPLES.length).toBeGreaterThanOrEqual(3);
    const axes = new Set(REFERENCES_EXEMPLES.map((r) => r.axe));
    expect([...axes].sort()).toEqual(["bornes", "ombrieres", "solaire"]);
    for (const r of REFERENCES_EXEMPLES) {
      expect(r.nom.trim()).not.toBe("");
      expect(r.ville.trim()).not.toBe("");
      expect(r.description.trim()).not.toBe("");
    }
  });

  it("a des noms uniques (insertion idempotente par nom)", () => {
    const noms = REFERENCES_EXEMPLES.map((r) => r.nom);
    expect(new Set(noms).size).toBe(noms.length);
  });
});
