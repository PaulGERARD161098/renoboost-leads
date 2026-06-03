"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import type { RunQualite } from "@/lib/database.types";

export async function createRun(input: {
  verticaleId: string;
  departement?: string | null;
  adresse?: string | null;
  rayonKm?: number | null;
  effectifMin?: number | null;
  budgetEur?: number | null;
  volumeCible?: number | null;
  isTest?: boolean;
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
      is_test: input.isTest ?? false,
      status: "demande",
      created_by: user?.id ?? null,
    })
    .select("id")
    .single();

  if (error) return { error: error.message };
  revalidatePath("/recherche");
  revalidatePath("/inbox");
  return { ok: true, runId: data.id };
}

/** Supprime une recherche et tous ses prospects. */
export async function deleteRun(runId: string) {
  const supabase = await createClient();
  const { error: leadsError } = await supabase
    .from("leads")
    .delete()
    .eq("run_id", runId);
  if (leadsError) return { error: leadsError.message };
  const { error } = await supabase.from("runs").delete().eq("id", runId);
  if (error) return { error: error.message };
  revalidatePath("/recherche");
  revalidatePath("/inbox");
  return { ok: true };
}

/** Met à jour les métadonnées d'une recherche (nom, note, archivage, qualité). */
export async function updateRun(
  runId: string,
  patch: {
    nom?: string | null;
    note?: string | null;
    archive?: boolean;
    qualite?: RunQualite | null;
  },
) {
  const supabase = await createClient();
  const fields: Record<string, unknown> = {};
  if ("nom" in patch) fields.nom = patch.nom?.trim() || null;
  if ("note" in patch) fields.note = patch.note?.trim() || null;
  if ("archive" in patch) fields.archive = patch.archive;
  if ("qualite" in patch) fields.qualite = patch.qualite ?? null;
  if (Object.keys(fields).length === 0) return { ok: true };

  const { error } = await supabase.from("runs").update(fields).eq("id", runId);
  if (error) return { error: error.message };
  revalidatePath("/recherche");
  revalidatePath("/inbox");
  return { ok: true };
}
