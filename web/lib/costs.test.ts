import { describe, expect, it } from "vitest";
import {
  COUT_CLAUDE_HAIKU_PAR_LEAD,
  COUT_PLACES_PAR_LEAD,
  COUT_RELANCE_PREDRAFT_EUR,
  coutRelances,
  cumulerCoutDetail,
  estimerCoutDetail,
  estimerCoutRun,
  formatEur,
  normaliserCoutDetail,
  predraftsRestantsSousBudget,
  sommeCoutDetail,
} from "@/lib/costs";

describe("budget IA des relances", () => {
  it("coutRelances = nb × coût unitaire (jamais négatif)", () => {
    expect(coutRelances(5)).toBeCloseTo(5 * COUT_RELANCE_PREDRAFT_EUR);
    expect(coutRelances(0)).toBe(0);
    expect(coutRelances(-3)).toBe(0);
  });

  it("plafond ≤ 0 → pas de limite (Infinity)", () => {
    expect(predraftsRestantsSousBudget(0, 10)).toBe(Infinity);
    expect(predraftsRestantsSousBudget(-1, 0)).toBe(Infinity);
  });

  it("respecte le budget restant et le borne à 0", () => {
    // 0,20 € / 0,02 € = 10 pré-rédactions/jour ; 4 déjà faites → 6 restantes.
    expect(predraftsRestantsSousBudget(0.2, 4)).toBe(6);
    expect(predraftsRestantsSousBudget(0.2, 10)).toBe(0);
    expect(predraftsRestantsSousBudget(0.2, 99)).toBe(0);
  });
});

describe("estimerCoutDetail", () => {
  it("ventile par API avec une fourchette bas/haut", () => {
    const lignes = estimerCoutDetail(100);
    expect(lignes.map((l) => l.cle)).toEqual([
      "places",
      "pappers",
      "dropcontact",
      "claude",
    ]);
    // Places : coût fixe (bas = haut).
    const places = lignes.find((l) => l.cle === "places")!;
    expect(places.bas).toBeCloseTo(100 * COUT_PLACES_PAR_LEAD);
    expect(places.haut).toBeCloseTo(100 * COUT_PLACES_PAR_LEAD);
    // Pappers / Dropcontact : optionnels → bas = 0, haut > 0.
    for (const cle of ["pappers", "dropcontact"] as const) {
      const l = lignes.find((x) => x.cle === cle)!;
      expect(l.bas).toBe(0);
      expect(l.haut).toBeGreaterThan(0);
    }
  });

  it("retourne 0 pour un volume nul ou invalide", () => {
    for (const v of [0, -5, Number.NaN]) {
      expect(estimerCoutDetail(v).every((l) => l.bas === 0 && l.haut === 0)).toBe(true);
    }
  });
});

describe("estimerCoutRun", () => {
  it("somme la ventilation par API", () => {
    const detail = estimerCoutDetail(200);
    const total = estimerCoutRun(200);
    expect(total.bas).toBeCloseTo(detail.reduce((s, l) => s + l.bas, 0));
    expect(total.haut).toBeCloseTo(detail.reduce((s, l) => s + l.haut, 0));
    // Bas = Places + Claude Haiku (postes optionnels à 0).
    expect(total.bas).toBeCloseTo(
      200 * (COUT_PLACES_PAR_LEAD + COUT_CLAUDE_HAIKU_PAR_LEAD),
    );
  });
});

describe("normaliserCoutDetail", () => {
  it("écarte les postes à 0 € et respecte l'ordre canonique", () => {
    const lignes = normaliserCoutDetail({
      claude: 1.2,
      places: 5,
      dropcontact: 0,
      pappers: 0.8,
    });
    expect(lignes.map((l) => l.cle)).toEqual(["places", "pappers", "claude"]);
  });

  it("tolère un détail absent, partiel ou aux clés inconnues", () => {
    expect(normaliserCoutDetail(null)).toEqual([]);
    expect(normaliserCoutDetail(undefined)).toEqual([]);
    expect(normaliserCoutDetail({})).toEqual([]);
    expect(normaliserCoutDetail({ inconnu: 9 } as Record<string, number>)).toEqual([]);
  });
});

describe("sommeCoutDetail / cumulerCoutDetail", () => {
  it("somme les postes connus", () => {
    expect(sommeCoutDetail({ places: 5, claude: 1, inconnu: 99 })).toBeCloseTo(6);
  });

  it("cumule plusieurs runs par poste", () => {
    const cumul = cumulerCoutDetail([
      { places: 5, claude: 1 },
      { places: 3, pappers: 2 },
      null,
      { dropcontact: 4 },
    ]);
    expect(cumul).toEqual({ places: 8, pappers: 2, dropcontact: 4, claude: 1 });
  });
});

describe("formatEur", () => {
  it("ajuste les décimales selon l'ordre de grandeur", () => {
    expect(formatEur(0.05)).toBe("0.05 €");
    expect(formatEur(2.5)).toBe("2.5 €");
    expect(formatEur(42)).toBe("42 €");
    expect(formatEur(Number.NaN)).toBe("—");
  });
});
