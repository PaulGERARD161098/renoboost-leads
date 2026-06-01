"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export interface VerticaleInput {
  nom: string;
  description: string;
  offre: string;
  secteursNaf: string[];
  effectifMin: number | null;
  signaux: string[];
  active: boolean;
}

/** Slug URL-safe dérivé du nom (a-z0-9 + tirets). */
function toSlug(nom: string): string {
  return nom
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
}

function buildConfig(input: VerticaleInput): Record<string, unknown> {
  return {
    offre: input.offre || null,
    secteurs_naf: input.secteursNaf,
    effectif_min: input.effectifMin,
    signaux: input.signaux,
  };
}

export async function createVerticale(input: VerticaleInput) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const base = toSlug(input.nom) || "cible";
  // Unicité du slug : suffixe court si collision.
  let slug = base;
  for (let i = 0; i < 5; i++) {
    const { data: clash } = await supabase
      .from("verticales")
      .select("id")
      .eq("slug", slug)
      .maybeSingle();
    if (!clash) break;
    slug = `${base}-${Math.random().toString(36).slice(2, 5)}`;
  }

  const { data, error } = await supabase
    .from("verticales")
    .insert({
      slug,
      nom: input.nom,
      description: input.description || null,
      config: buildConfig(input),
      active: input.active,
      created_by: user?.id ?? null,
    })
    .select("id")
    .single();

  if (error) return { error: error.message };
  revalidatePath("/cibles");
  redirect(`/cibles/${data.id}`);
}

export async function updateVerticale(id: string, input: VerticaleInput) {
  const supabase = await createClient();
  const { error } = await supabase
    .from("verticales")
    .update({
      nom: input.nom,
      description: input.description || null,
      config: buildConfig(input),
      active: input.active,
    })
    .eq("id", id);

  if (error) return { error: error.message };
  revalidatePath("/cibles");
  revalidatePath(`/cibles/${id}`);
  return { ok: true };
}

export async function toggleVerticaleActive(id: string, active: boolean) {
  const supabase = await createClient();
  const { error } = await supabase
    .from("verticales")
    .update({ active })
    .eq("id", id);
  if (error) return { error: error.message };
  revalidatePath("/cibles");
  revalidatePath(`/cibles/${id}`);
  return { ok: true };
}
