import { describe, it, expect } from "vitest";
import {
  categoriser,
  opportunitesAutourDesRdv,
  pointsTournee,
  type LeadCarto,
} from "@/lib/tournees";

const lead = (over: Partial<LeadCarto> = {}): LeadCarto => ({
  id: "x",
  entreprise: "X",
  ville: null,
  statut: "valide",
  score: 80,
  latitude: 50.37,
  longitude: 3.08,
  rdv_at: null,
  contact_tel: null,
  ...over,
});

describe("categoriser", () => {
  it("RDV pris → rdv ; répondu ou top lead → chaud ; à relancer → tiède", () => {
    expect(categoriser(lead({ statut: "rdv_pris" }))).toBe("rdv");
    expect(categoriser(lead({ statut: "repondu" }))).toBe("chaud");
    expect(categoriser(lead({ statut: "valide", score: 90 }))).toBe("chaud");
    expect(categoriser(lead({ statut: "a_relancer" }))).toBe("tiede");
  });

  it("exclut conclus/écartés et les leads tièdes non scorés", () => {
    expect(categoriser(lead({ statut: "gagne" }))).toBeNull();
    expect(categoriser(lead({ statut: "perdu" }))).toBeNull();
    expect(categoriser(lead({ statut: "ecarte" }))).toBeNull();
    expect(categoriser(lead({ statut: "valide", score: 50 }))).toBeNull();
  });
});

describe("pointsTournee", () => {
  it("écarte les coordonnées hors France et trie RDV > chaud > tiède", () => {
    const pts = pointsTournee([
      lead({ id: "tiede", statut: "a_relancer" }),
      lead({ id: "horsfr", statut: "rdv_pris", latitude: 0, longitude: 0 }),
      lead({ id: "rdv", statut: "rdv_pris" }),
      lead({ id: "chaud", statut: "repondu" }),
      lead({ id: "sanscoord", latitude: null, longitude: null }),
    ]);
    expect(pts.map((p) => p.lead.id)).toEqual(["rdv", "chaud", "tiede"]);
  });
});

describe("opportunitesAutourDesRdv", () => {
  it("regroupe les prospects dans le rayon autour de chaque RDV", () => {
    const pts = pointsTournee([
      lead({ id: "rdv", statut: "rdv_pris", latitude: 50.37, longitude: 3.08 }),
      lead({ id: "proche", statut: "repondu", latitude: 50.38, longitude: 3.06 }),
      lead({ id: "loin", statut: "repondu", latitude: 48.85, longitude: 2.35 }),
    ]);
    const opp = opportunitesAutourDesRdv(pts, 20);
    expect(opp).toHaveLength(1);
    expect(opp[0].rdv.lead.id).toBe("rdv");
    expect(opp[0].aProximite.map((p) => p.lead.id)).toEqual(["proche"]);
  });

  it("ignore un RDV sans prospect à proximité", () => {
    const pts = pointsTournee([
      lead({ id: "rdv", statut: "rdv_pris", latitude: 50.37, longitude: 3.08 }),
    ]);
    expect(opportunitesAutourDesRdv(pts, 20)).toHaveLength(0);
  });
});
