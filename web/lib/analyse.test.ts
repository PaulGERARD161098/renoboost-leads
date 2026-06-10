import { describe, it, expect } from "vitest";
import { potentielsDepuisAnalyse, type AnalyseResult } from "@/lib/analyse";
import type { ComptageBornes } from "@/lib/potentiel";

const sansBornes: ComptageBornes = { sur_site: 0, voisinage_1km: 0, rayon_10km: 0, types: [] };

describe("potentielsDepuisAnalyse", () => {
  it("score une usine type : grande toiture plate + parking, pas de bornes", () => {
    const terrain: AnalyseResult["terrain"] = {
      toiture: { surface_m2_estimee: 5000, type: "plate" },
      parking: { surface_m2_estimee: 2000, nb_places_estimee: null, ombrieres_existantes: false },
      bornes_ve: { presentes: false },
    };
    const p = potentielsDepuisAnalyse(terrain, sansBornes);
    expect(p.version).toBe(2);
    // 5000 m² × 0.7 (plate) = 3500 m² exploitables → base 10, +2 plate, clampé 10.
    expect(p.solaire.score).toBe(10);
    expect(p.solaire.surface_exploitable_m2).toBe(3500);
    // 2000 m² / 25 = 80 places → base 7, usage indéterminé (pas de bonus).
    expect(p.ombrieres.score).toBe(7);
    expect(p.ombrieres.nb_places).toBe(80);
    // Aucune borne sur site (manque 4), zone sans adoption (0) → 4.
    expect(p.bornes.score).toBe(4);
    expect(p.meilleur).toBe("solaire");
    expect(p.synthese).toContain("analyse d'image Magellan");
    expect(p.image_url).toBeUndefined();
  });

  it("normalise le vocabulaire toiture du prompt vision (« inclinée » → ratio 0.55)", () => {
    const p = potentielsDepuisAnalyse(
      { toiture: { surface_m2_estimee: 1000, type: "inclinée" } },
      sansBornes,
    );
    expect(p.solaire.surface_exploitable_m2).toBe(550);
    expect(p.solaire.type_toiture).toBe("inclinee");
  });

  it("plafonne les ombrières à 1 si déjà présentes sur le parking", () => {
    const p = potentielsDepuisAnalyse(
      { parking: { surface_m2_estimee: 6000, ombrieres_existantes: true } },
      sansBornes,
    );
    expect(p.ombrieres.score).toBe(1);
    expect(p.ombrieres.justification).toContain("déjà présentes");
  });

  it("croise les bornes vues sur l'image avec le comptage IRVE", () => {
    const p = potentielsDepuisAnalyse(
      { bornes_ve: { presentes: true, nb_estime: 4 } },
      { sur_site: 1, voisinage_1km: 2, rayon_10km: 12, types: ["22 kW"] },
    );
    // max(1 API, 4 vision) = 4 sur site → manque 1 ; adoption 3 (voisinage) + 3 (≥10 à 10 km) → 6, clampé.
    expect(p.bornes.sur_site).toBe(4);
    expect(p.bornes.score).toBe(7);
  });

  it("reste défensif sur un terrain vide ou absent", () => {
    const p = potentielsDepuisAnalyse(undefined, sansBornes);
    expect(p.solaire.score).toBe(0);
    expect(p.ombrieres.score).toBe(0);
    expect(p.bornes.score).toBe(4);
    expect(p.meilleur).toBe("bornes");
  });
});
