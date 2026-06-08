import { describe, it, expect } from "vitest";
import {
  actionRecommandeePourCategorie,
  transitionForCategorie,
} from "@/lib/reply-actions";
import type { ReplyCategorie } from "@/lib/database.types";

const CATEGORIES: ReplyCategorie[] = [
  "interesse",
  "info",
  "plus_tard",
  "mauvais_interlocuteur",
  "pas_interesse",
  "absence",
  "autre",
];

describe("transitionForCategorie", () => {
  it("propose RDV pris (non auto) pour un prospect intéressé", () => {
    const tr = transitionForCategorie("interesse");
    expect(tr).toEqual({ statut: "rdv_pris", label: "Marquer RDV pris", auto: false });
  });

  it("planifie une relance auto pour « plus tard »", () => {
    const tr = transitionForCategorie("plus_tard");
    expect(tr?.statut).toBe("a_relancer");
    expect(tr?.auto).toBe(true);
    expect(tr?.relanceDansJours).toBe(21);
  });

  it("propose un écartement validé (jamais auto) pour les refus/erreurs", () => {
    for (const c of ["pas_interesse", "absence", "mauvais_interlocuteur"] as ReplyCategorie[]) {
      const tr = transitionForCategorie(c);
      expect(tr?.statut).toBe("ecarte");
      expect(tr?.auto).toBe(false);
    }
  });

  it("ne propose pas de transition pour info / autre", () => {
    expect(transitionForCategorie("info")).toBeNull();
    expect(transitionForCategorie("autre")).toBeNull();
  });

  it("seul « plus_tard » est automatisable", () => {
    const autos = CATEGORIES.filter((c) => transitionForCategorie(c)?.auto);
    expect(autos).toEqual(["plus_tard"]);
  });
});

describe("actionRecommandeePourCategorie", () => {
  it("renvoie une recommandation non vide pour chaque catégorie", () => {
    for (const c of CATEGORIES) {
      expect(actionRecommandeePourCategorie(c).length).toBeGreaterThan(0);
    }
  });

  it("oriente vers le RDV quand le prospect est intéressé", () => {
    expect(actionRecommandeePourCategorie("interesse")).toMatch(/RDV/i);
  });
});
