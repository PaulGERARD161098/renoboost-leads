import { describe, it, expect } from "vitest";
import {
  INTENTIONS,
  SIGNAL_TYPES_PAR_INTENTION,
  appliquerIntentions,
  intentionParId,
  intentionsConcernantSignal,
  intentionsDeConfig,
  signalTypesPourIntentions,
  type IntentionId,
} from "@/lib/intentions";

const VIDE = { secteursNaf: [], signaux: [], effectifMin: null };

describe("catalogue INTENTIONS", () => {
  it("expose 3 intentions à ids uniques et non vides", () => {
    const ids = INTENTIONS.map((i) => i.id);
    expect(ids).toEqual(["flotte_ve", "conso_elec", "fiscal"]);
    expect(new Set(ids).size).toBe(ids.length);
    for (const i of INTENTIONS) {
      expect(i.secteursNaf.length).toBeGreaterThan(0);
      expect(i.signaux.length).toBeGreaterThan(0);
      expect(i.effectifMinSuggere).toBeGreaterThan(0);
    }
  });

  it("intentionParId résout un id connu, undefined sinon", () => {
    expect(intentionParId("flotte_ve")?.label).toBe("Électrifier sa flotte");
    expect(intentionParId("inconnu")).toBeUndefined();
  });
});

describe("appliquerIntentions", () => {
  it("compile NAF + signaux + effectif suggéré depuis un champ vide", () => {
    const res = appliquerIntentions(["flotte_ve"], VIDE);
    const ref = intentionParId("flotte_ve")!;
    expect(res.secteursNaf).toEqual(ref.secteursNaf);
    expect(res.signaux).toEqual(ref.signaux);
    expect(res.effectifMin).toBe(ref.effectifMinSuggere);
  });

  it("est additif : conserve la saisie existante", () => {
    const res = appliquerIntentions(["flotte_ve"], {
      secteursNaf: ["99"],
      signaux: ["mon signal"],
      effectifMin: 5,
    });
    expect(res.secteursNaf[0]).toBe("99");
    expect(res.secteursNaf).toContain("49");
    expect(res.signaux[0]).toBe("mon signal");
    expect(res.effectifMin).toBe(5); // ne réécrit pas un effectif déjà saisi
  });

  it("déduplique (insensible casse/espaces) et reste idempotent", () => {
    const once = appliquerIntentions(["conso_elec"], VIDE);
    const twice = appliquerIntentions(["conso_elec"], once);
    expect(twice.secteursNaf).toEqual(once.secteursNaf);
    expect(twice.signaux).toEqual(once.signaux);

    const avecDoublon = appliquerIntentions(["flotte_ve"], {
      secteursNaf: [" 49 "],
      signaux: [],
      effectifMin: null,
    });
    expect(avecDoublon.secteursNaf.filter((n) => n.trim() === "49")).toHaveLength(1);
  });

  it("fusionne plusieurs intentions sans doublon de NAF partagé", () => {
    const res = appliquerIntentions(["conso_elec", "fiscal"], VIDE);
    // « 25 » (produits métalliques) est dans les deux → présent une seule fois.
    expect(res.secteursNaf.filter((n) => n === "25")).toHaveLength(1);
  });

  it("suggère l'effectif le plus prudent (max) si vide", () => {
    const ids: IntentionId[] = ["flotte_ve", "conso_elec"];
    const res = appliquerIntentions(ids, VIDE);
    const attendu = Math.max(
      ...ids.map((id) => intentionParId(id)!.effectifMinSuggere),
    );
    expect(res.effectifMin).toBe(attendu);
  });

  it("ignore silencieusement un id inconnu", () => {
    const res = appliquerIntentions(["zzz" as IntentionId], VIDE);
    expect(res).toEqual(VIDE);
  });
});

describe("pont intentions ⟶ veille", () => {
  it("couvre toutes les intentions du catalogue", () => {
    for (const i of INTENTIONS) {
      expect(SIGNAL_TYPES_PAR_INTENTION[i.id]).toBeDefined();
    }
    // fiscal n'a pas de signal direct (profil financier, pas un événement).
    expect(SIGNAL_TYPES_PAR_INTENTION.fiscal).toEqual([]);
  });

  it("signalTypesPourIntentions fait l'union dédupliquée", () => {
    const types = signalTypesPourIntentions(["flotte_ve", "conso_elec"]);
    // electrification est dans les deux → une seule fois.
    expect(types.filter((t) => t === "electrification")).toHaveLength(1);
    expect(types).toContain("ve_flotte");
    expect(types).toContain("ombrieres");
  });

  it("signalTypesPourIntentions ignore les ids inconnus et le fiscal seul", () => {
    expect(signalTypesPourIntentions(["fiscal"])).toEqual([]);
    expect(signalTypesPourIntentions(["zzz"])).toEqual([]);
  });

  it("intentionsConcernantSignal est la réciproque", () => {
    expect(intentionsConcernantSignal("ve_flotte")).toEqual(["flotte_ve"]);
    expect(intentionsConcernantSignal("electrification").sort()).toEqual([
      "conso_elec",
      "flotte_ve",
    ]);
    expect(intentionsConcernantSignal(null)).toEqual([]);
    expect(intentionsConcernantSignal("inexistant")).toEqual([]);
  });
});

describe("intentionsDeConfig", () => {
  it("lit et type les intentions d'une config JSONB", () => {
    const res = intentionsDeConfig({ intentions: ["flotte_ve", "fiscal"] });
    expect(res.map((i) => i.id)).toEqual(["flotte_ve", "fiscal"]);
  });

  it("ignore les ids inconnus et les valeurs non-string", () => {
    const res = intentionsDeConfig({ intentions: ["flotte_ve", "zzz", 42] });
    expect(res.map((i) => i.id)).toEqual(["flotte_ve"]);
  });

  it("renvoie [] si pas d'intentions", () => {
    expect(intentionsDeConfig(null)).toEqual([]);
    expect(intentionsDeConfig({})).toEqual([]);
    expect(intentionsDeConfig({ intentions: "flotte_ve" })).toEqual([]);
  });
});
