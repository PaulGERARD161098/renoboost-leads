import { describe, it, expect } from "vitest";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { VeilleSignal } from "@/lib/database.types";
import { estSignalVE, signauxDuLead, TYPES_SIGNAL_VE } from "@/lib/veille-signaux";

describe("estSignalVE", () => {
  it("vrai pour les types d'électrification", () => {
    for (const type of TYPES_SIGNAL_VE) {
      expect(estSignalVE({ type })).toBe(true);
    }
  });
  it("faux pour les autres types ou type absent", () => {
    expect(estSignalVE({ type: "ombrieres" })).toBe(false);
    expect(estSignalVE({ type: "autre" })).toBe(false);
    expect(estSignalVE({ type: null })).toBe(false);
  });
});

// Stub Supabase : la chaîne from().select().eq().order() résout en { data }.
function fakeSupabase(rows: VeilleSignal[] | null): SupabaseClient {
  const chain = {
    from: () => chain,
    select: () => chain,
    eq: () => chain,
    order: () => Promise.resolve({ data: rows }),
  };
  return chain as unknown as SupabaseClient;
}

describe("signauxDuLead", () => {
  it("renvoie les signaux rattachés au lead", async () => {
    const rows = [{ id: "s1", type: "ve_flotte" } as VeilleSignal];
    const out = await signauxDuLead(fakeSupabase(rows), "lead-1");
    expect(out).toHaveLength(1);
    expect(out[0].id).toBe("s1");
  });
  it("renvoie un tableau vide quand data est null", async () => {
    const out = await signauxDuLead(fakeSupabase(null), "lead-1");
    expect(out).toEqual([]);
  });
});
