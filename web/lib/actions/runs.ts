"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";

export async function createRun(input: {
  verticaleId: string;
  departement?: string | null;
  adresse?: string | null;
  rayonKm?: number | null;
  effectifMin?: number | null;
  budgetEur?: number | null;
  volumeCible?: number | null;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Zone : autour d'une adresse (point GPS géocodé) si fournie, sinon département.
  const zone: Record<string, unknown> = {
    effectif_min: input.effectifMin ?? null,
  };
  if (input.adresse && input.adresse.trim()) {
    zone.adresse = input.adresse.trim();
    zone.rayon_par_point_km = input.rayonKm ?? 10;
  } else {
    zone.departement = input.departement ?? null;
  }

  const { data, error } = await supabase
    .from("runs")
    .insert({
      verticale_id: input.verticaleId,
      zone,
      volume_cible: input.volumeCible ?? null,
      budget_eur: input.budgetEur ?? null,
      status: "demande",
      created_by: user?.id ?? null,
    })
    .select("id")
    .single();

  if (error) return { error: error.message };
  revalidatePath("/recherche");
  return { ok: true, runId: data.id };
}
