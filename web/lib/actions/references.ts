"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { REFERENCES_EXEMPLES } from "@/lib/references-demo";

export type ReferenceInput = {
  nom: string;
  ville: string;
  axe: "solaire" | "ombrieres" | "bornes";
  description: string;
};

/** Géocode une ville via la BAN (gratuit), best-effort → [lat, lng] ou nulls. */
async function geocodeVille(ville: string): Promise<{ lat: number | null; lng: number | null }> {
  if (!ville) return { lat: null, lng: null };
  try {
    const res = await fetch(
      `https://api-adresse.data.gouv.fr/search/?q=${encodeURIComponent(ville)}&type=municipality&limit=1`,
    );
    if (res.ok) {
      const gj = await res.json();
      const coords = gj.features?.[0]?.geometry?.coordinates;
      if (Array.isArray(coords) && coords.length === 2) {
        return { lat: Number(coords[1]), lng: Number(coords[0]) };
      }
    }
  } catch {
    // Best-effort : la référence reste citable sans distance.
  }
  return { lat: null, lng: null };
}

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

  const ville = input.ville.trim();
  const { lat, lng } = await geocodeVille(ville);

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

/**
 * Amorce la brique « preuve sociale » quand elle est vide : insère des exemples
 * réalistes (Hauts-de-France), géocodés, en sautant ceux déjà présents (par nom).
 * Réversible — chaque référence reste supprimable.
 */
export async function chargerReferencesExemples() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { data: existantes } = await supabase
    .from("references_chantiers")
    .select("nom");
  const dejaLa = new Set(
    ((existantes as { nom: string }[] | null) ?? []).map((r) => r.nom),
  );
  const aCreer = REFERENCES_EXEMPLES.filter((r) => !dejaLa.has(r.nom));
  if (aCreer.length === 0) return { ok: true, ajoutes: 0 };

  const lignes = await Promise.all(
    aCreer.map(async (r) => {
      const { lat, lng } = await geocodeVille(r.ville);
      return {
        nom: r.nom,
        ville: r.ville,
        lat,
        lng,
        axe: r.axe,
        description: r.description,
        created_by: user?.id ?? null,
      };
    }),
  );
  const { error } = await supabase.from("references_chantiers").insert(lignes);
  if (error) return { error: error.message };
  revalidatePath("/cibles");
  return { ok: true, ajoutes: lignes.length };
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
