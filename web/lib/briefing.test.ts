import { describe, it, expect } from "vitest";
import { prochainesDeadlines } from "@/lib/briefing";

// Référence fixe (heure de Paris) : 2026-06-08.
const NOW = new Date("2026-06-08T09:00:00+02:00");

describe("prochainesDeadlines", () => {
  it("calcule les jours restants et le retard", () => {
    const res = prochainesDeadlines(
      [
        { label: "Closing client A", date: "2026-06-10" }, // dans 2 j
        { label: "Relance B", date: "2026-06-05" }, // en retard de 3 j
        { label: "Démo C", date: "2026-06-08" }, // aujourd'hui
      ],
      NOW,
    );
    // Trié du plus urgent (retard) au plus lointain.
    expect(res.map((d) => d.label)).toEqual(["Relance B", "Démo C", "Closing client A"]);
    expect(res[0]).toMatchObject({ joursRestants: -3, enRetard: true });
    expect(res[1]).toMatchObject({ joursRestants: 0, enRetard: false });
    expect(res[2]).toMatchObject({ joursRestants: 2, enRetard: false });
  });

  it("ignore les entrées sans label ou à date invalide", () => {
    const res = prochainesDeadlines(
      [
        { label: "  ", date: "2026-06-10" },
        { label: "Sans date", date: "" },
        { label: "Mauvais format", date: "10/06/2026" },
        { label: "Valide", date: "2026-06-12" },
      ],
      NOW,
    );
    expect(res.map((d) => d.label)).toEqual(["Valide"]);
  });

  it("borne le nombre d'échéances affichées", () => {
    const many = Array.from({ length: 8 }, (_, i) => ({
      label: `D${i}`,
      date: `2026-06-${String(10 + i).padStart(2, "0")}`,
    }));
    expect(prochainesDeadlines(many, NOW, 4)).toHaveLength(4);
  });

  it("renvoie [] sur entrée vide ou nulle", () => {
    expect(prochainesDeadlines([], NOW)).toEqual([]);
    expect(prochainesDeadlines(null, NOW)).toEqual([]);
    expect(prochainesDeadlines(undefined, NOW)).toEqual([]);
  });
});
