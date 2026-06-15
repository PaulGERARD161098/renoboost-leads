import { describe, it, expect } from "vitest";
import {
  statsParAngle,
  angleGagnantParCible,
  liftAngleAppris,
  type LeadStat,
  type LeadStatCible,
} from "@/lib/stats-angles";

const lead = (
  statut: LeadStat["statut"],
  mail_angle: LeadStat["mail_angle"],
  extra: Partial<LeadStat> = {},
): LeadStat => ({ statut, mail_angle, sent_at: null, replied_at: null, ...extra });

const leadC = (
  verticale_id: string | null,
  statut: LeadStat["statut"],
  mail_angle: LeadStat["mail_angle"],
): LeadStatCible => ({ verticale_id, statut, mail_angle, sent_at: null, replied_at: null });

describe("statsParAngle", () => {
  it("agrège envoyés/réponses/gagnés par angle et trie par taux", () => {
    const rows = statsParAngle([
      lead("envoye", "solaire"),
      lead("envoye", "solaire"),
      lead("repondu", "solaire"),
      lead("gagne", "bornes"),
      lead("envoye", "bornes"),
      lead("nouveau", "bornes"), // jamais contacté : ignoré
    ]);
    const bornes = rows.find((r) => r.angle === "bornes")!;
    const solaire = rows.find((r) => r.angle === "solaire")!;
    expect(bornes).toMatchObject({ envoyes: 2, repondus: 1, tauxReponse: 50, gagnes: 1 });
    expect(solaire).toMatchObject({ envoyes: 3, repondus: 1, tauxReponse: 33, gagnes: 0 });
    expect(rows[0].angle).toBe("bornes"); // meilleur taux d'abord
  });

  it("compte les anciens leads sans angle à part, en dernier", () => {
    const rows = statsParAngle([
      lead("repondu", null),
      lead("envoye", "ombrieres", { replied_at: "2026-06-01T00:00:00Z" }),
    ]);
    expect(rows.at(-1)?.angle).toBe("sans_angle");
    expect(rows.find((r) => r.angle === "ombrieres")?.repondus).toBe(1);
  });

  it("rien d'envoyé → tableau vide", () => {
    expect(statsParAngle([lead("nouveau", "solaire")])).toEqual([]);
  });
});

describe("angleGagnantParCible", () => {
  // Cible A : bornes (4 envois, 3 réponses = 75%) bat solaire (4 envois, 1 rép = 25%).
  const cibleA = [
    leadC("A", "repondu", "bornes"),
    leadC("A", "repondu", "bornes"),
    leadC("A", "rdv_pris", "bornes"),
    leadC("A", "envoye", "bornes"),
    leadC("A", "repondu", "solaire"),
    leadC("A", "envoye", "solaire"),
    leadC("A", "envoye", "solaire"),
    leadC("A", "envoye", "solaire"),
  ];

  it("recommande l'angle au meilleur taux par cible, avec l'avance sur le 2e", () => {
    const recos = angleGagnantParCible(cibleA);
    expect(recos).toHaveLength(1);
    expect(recos[0]).toMatchObject({
      verticaleId: "A",
      angle: "bornes",
      envoyes: 4,
      tauxReponse: 75,
      avance: 50, // 75% − 25%
    });
  });

  it("ignore les angles sous le seuil d'envois (pas assez de signal)", () => {
    // bornes n'a que 2 envois (< seuil par défaut) → pas de reco.
    const recos = angleGagnantParCible([
      leadC("A", "repondu", "bornes"),
      leadC("A", "repondu", "bornes"),
    ]);
    expect(recos).toEqual([]);
  });

  it("avance = null quand un seul angle a assez d'envois", () => {
    const recos = angleGagnantParCible([
      leadC("A", "repondu", "bornes"),
      leadC("A", "repondu", "bornes"),
      leadC("A", "envoye", "bornes"),
      leadC("A", "envoye", "bornes"),
      leadC("A", "repondu", "solaire"), // 1 seul envoi solaire < seuil
    ]);
    expect(recos[0]).toMatchObject({ angle: "bornes", avance: null });
  });

  it("ignore les leads sans cible et sépare les cibles", () => {
    const recos = angleGagnantParCible([
      ...cibleA,
      leadC(null, "repondu", "solaire"), // sans cible : ignoré
      leadC("B", "repondu", "ombrieres"),
      leadC("B", "repondu", "ombrieres"),
      leadC("B", "envoye", "ombrieres"),
      leadC("B", "envoye", "ombrieres"),
    ]);
    const ids = recos.map((r) => r.verticaleId).sort();
    expect(ids).toEqual(["A", "B"]);
    expect(recos.find((r) => r.verticaleId === "B")?.angle).toBe("ombrieres");
  });

  it("abaisser le seuil débloque des recos sur petits volumes", () => {
    const recos = angleGagnantParCible(
      [leadC("A", "repondu", "bornes"), leadC("A", "envoye", "bornes")],
      2,
    );
    expect(recos[0]).toMatchObject({ angle: "bornes", envoyes: 2 });
  });
});

describe("liftAngleAppris", () => {
  // Cible A : bornes gagne (6 envois, 4 réponses = 67%) vs solaire (4, 0 = 0%).
  const dataset = [
    leadC("A", "repondu", "bornes"),
    leadC("A", "repondu", "bornes"),
    leadC("A", "repondu", "bornes"),
    leadC("A", "rdv_pris", "bornes"),
    leadC("A", "envoye", "bornes"),
    leadC("A", "envoye", "bornes"),
    leadC("A", "envoye", "solaire"),
    leadC("A", "envoye", "solaire"),
    leadC("A", "envoye", "solaire"),
    leadC("A", "envoye", "solaire"),
  ];

  it("mesure le lift : aligné sur l'angle appris vs autre", () => {
    const lift = liftAngleAppris(dataset)!;
    expect(lift.aligne).toMatchObject({ envoyes: 6, repondus: 4, taux: 67 });
    expect(lift.autre).toMatchObject({ envoyes: 4, repondus: 0, taux: 0 });
    expect(lift.lift).toBe(67);
  });

  it("null sans angle gagnant fiable (pas assez d'envois)", () => {
    expect(liftAngleAppris([leadC("A", "repondu", "bornes")])).toBeNull();
  });

  it("null s'il manque un côté du comparant (tout aligné)", () => {
    // bornes gagne et tous les leads sont en bornes → pas de groupe « autre ».
    expect(
      liftAngleAppris([
        leadC("A", "repondu", "bornes"),
        leadC("A", "repondu", "bornes"),
        leadC("A", "envoye", "bornes"),
        leadC("A", "envoye", "bornes"),
      ]),
    ).toBeNull();
  });
});
