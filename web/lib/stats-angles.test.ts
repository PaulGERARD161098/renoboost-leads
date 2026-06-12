import { describe, it, expect } from "vitest";
import { statsParAngle, type LeadStat } from "@/lib/stats-angles";

const lead = (
  statut: LeadStat["statut"],
  mail_angle: LeadStat["mail_angle"],
  extra: Partial<LeadStat> = {},
): LeadStat => ({ statut, mail_angle, sent_at: null, replied_at: null, ...extra });

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
