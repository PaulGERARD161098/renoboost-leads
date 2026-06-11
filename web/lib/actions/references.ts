"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";

export type ReferenceInput = {
  nom: string;
  ville: string;
  axe: "solaire" | "ombrieres" | "bornes";
  description: string;
};

/**
 * Crée une référence chantier. La ville est géocodée (BAN, gratuit) pour que
 * la référence soit triable par distance au prospect.
 */
export async function creerReference(input: ReferenceInput) {
  const nom = input.nom.trim();
  if (!nom) return { error: "Le nom est obligatoire." };
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  let lat: number | null = null;
  let lng: number | null = null;
  const ville = input.ville.trim();
  if (ville) {
    try {
      const res = await fetch(
        `https://api-adresse.data.gouv.fr/search/?q=${encodeURIComponent(ville)}&type=municipality&limit=1`,
      );
      if (res.ok) {
        const gj = await res.json();
        const coords = gj.features?.[0]?.geometry?.coordinates;
        if (Array.isArray(coords) && coords.length === 2) {
          lng = Number(coords[0]);
          lat = Number(coords[1]);
        }
      }
    } catch {
      // Géocodage best-effort : la référence reste citable sans distance.
    }
  }

  const { error } = await supabase.from("references_chantiers").insert({
    nom,
    ville: ville || null,
    lat,
    lng,
    axe: input.axe,
    description: input.description.trim() || null,
    created_by: user?.id ?? null,
  });
  if (error) return { error: error.message };
  revalidatePath("/cibles");
  return { ok: true, geocode: lat != null };
}

export async function toggleReference(id: string, actif: boolean) {
  const supabase = await createClient();
  const { error } = await supabase
    .from("references_chantiers")
    .update({ actif })
    .eq("id", id);
  if (error) return { error: error.message };
  revalidatePath("/cibles");
  return { ok: true };
}

export async function supprimerReference(id: string) {
  const supabase = await createClient();
  const { error } = await supabase.from("references_chantiers").delete().eq("id", id);
  if (error) return { error: error.message };
  revalidatePath("/cibles");
  return { ok: true };
}
