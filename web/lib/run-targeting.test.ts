import { describe, it, expect } from "vitest";
import {
  EFFECTIF_PRESETS,
  EFFECTIF_MAX_ABSOLU,
  VOLUME_MAX,
  presetParId,
  presetPour,
  effectifLabel,
  validerCiblage,
} from "@/lib/run-targeting";

describe("presetParId", () => {
  it("retourne le preset demandé", () => {
    expect(presetParId("pme").min).toBe(10);
    expect(presetParId("pme").max).toBe(250);
  });
  it("retombe sur « custom » pour un id inconnu", () => {
    // @ts-expect-error test d'un id hors union
    expect(presetParId("zzz").id).toBe("custom");
  });
});

describe("presetPour", () => {
  it("reconnaît la tranche PME", () => {
    expect(presetPour(10, 250)).toBe("pme");
    expect(presetPour(10, 49)).toBe("petites");
    expect(presetPour(250, 4999)).toBe("eti");
  });
  it("renvoie custom hors preset connu", () => {
    expect(presetPour(5, 5000)).toBe("custom");
    expect(presetPour(10, null)).toBe("custom");
    expect(presetPour(null, null)).toBe("custom");
  });
});

describe("effectifLabel", () => {
  it("formate les quatre cas de bornes", () => {
    expect(effectifLabel(null, null)).toBe("Tous effectifs");
    expect(effectifLabel(10, 250)).toBe("10–250 salariés");
    expect(effectifLabel(100, null)).toBe("≥ 100 salariés (sans plafond)");
    expect(effectifLabel(null, 50)).toBe("≤ 50 salariés");
  });
});

describe("validerCiblage — erreurs bloquantes", () => {
  it("ne bloque pas un ciblage PME standard", () => {
    const v = validerCiblage({
      effectifMin: 10,
      effectifMax: 250,
      volume: 100,
      budgetEur: 50,
    });
    expect(v.erreurs).toEqual([]);
  });
  it("bloque min > max", () => {
    const v = validerCiblage({
      effectifMin: 300,
      effectifMax: 50,
      volume: 100,
      budgetEur: null,
    });
    expect(v.erreurs.some((e) => e.includes("supérieur"))).toBe(true);
  });
  it("bloque un effectif hors plage absolue", () => {
    const v = validerCiblage({
      effectifMin: -1,
      effectifMax: EFFECTIF_MAX_ABSOLU + 1,
      volume: 1,
      budgetEur: null,
    });
    expect(v.erreurs.length).toBeGreaterThanOrEqual(2);
  });
  it("bloque un volume hors 1..MAX", () => {
    expect(
      validerCiblage({ effectifMin: null, effectifMax: null, volume: 0, budgetEur: null })
        .erreurs.some((e) => e.includes("Volume")),
    ).toBe(true);
    expect(
      validerCiblage({
        effectifMin: null,
        effectifMax: null,
        volume: VOLUME_MAX + 1,
        budgetEur: null,
      }).erreurs.some((e) => e.includes("Volume")),
    ).toBe(true);
  });
  it("bloque un budget négatif", () => {
    const v = validerCiblage({
      effectifMin: null,
      effectifMax: null,
      volume: 10,
      budgetEur: -5,
    });
    expect(v.erreurs.some((e) => e.includes("négatif"))).toBe(true);
  });
});

describe("validerCiblage — alertes non bloquantes (cœur de cible PME)", () => {
  it("alerte quand min ≥ 100 (ETI / grands groupes)", () => {
    const v = validerCiblage({
      effectifMin: 100,
      effectifMax: 250,
      volume: 50,
      budgetEur: null,
    });
    expect(v.erreurs).toEqual([]);
    expect(v.alertes.some((a) => a.includes("cœur de cible"))).toBe(true);
  });
  it("alerte sur l'absence de plafond d'effectif", () => {
    const v = validerCiblage({
      effectifMin: 10,
      effectifMax: null,
      volume: 50,
      budgetEur: null,
    });
    expect(v.alertes.some((a) => a.includes("Pas de plafond"))).toBe(true);
  });
  it("alerte budget sous l'estimation basse, sauf en test", () => {
    const base = {
      effectifMin: 10,
      effectifMax: 250,
      volume: 50,
      budgetEur: 20,
      coutEstimeBas: 80,
    };
    expect(validerCiblage(base).alertes.some((a) => a.includes("Budget plafond"))).toBe(
      true,
    );
    expect(
      validerCiblage({ ...base, isTest: true }).alertes.some((a) =>
        a.includes("Budget plafond"),
      ),
    ).toBe(false);
  });
});

it("les presets exposent toujours un cœur de cible PME 10–250", () => {
  const pme = EFFECTIF_PRESETS.find((p) => p.id === "pme");
  expect(pme).toMatchObject({ min: 10, max: 250 });
});
