"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";

/** Enregistre une zone cible réutilisable (nom + adresse + rayon). */
export async function createZoneCible(input: {
  nom: string;
  adresse: string;
  rayonKm: number;
}) {
  const nom = input.nom.trim();
  const adresse = input.adresse.trim();
  if (!nom || !adresse) return { error: "Nom et adresse requis" };
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  const { error } = await supabase.from("zones_cibles").insert({
    nom,
    adresse,
    rayon_km: input.rayonKm || 10,
    created_by: user?.id ?? null,
  });
  if (error) return { error: error.message };
  revalidatePath("/recherche");
  return { ok: true };
}

export async function deleteZoneCible(id: string) {
  const supabase = await createClient();
  const { error } = await supabase.from("zones_cibles").delete().eq("id", id);
  if (error) return { error: error.message };
  revalidatePath("/recherche");
  return { ok: true };
}
