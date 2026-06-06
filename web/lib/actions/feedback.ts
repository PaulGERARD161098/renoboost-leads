"use server";

import { createClient } from "@/lib/supabase/server";
import type { RetourSource } from "@/lib/database.types";

// Empile un retour dans la file `retours` (drainée par Claude → correctifs
// proposés, jamais appliqués sans validation de Paul). Best-effort.
export async function logRetour(input: {
  source: RetourSource;
  texte: string;
  page?: string | null;
}) {
  const texte = input.texte?.trim();
  if (!texte) return { error: "Retour vide." };
  try {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (!user) return { error: "Non authentifié." };
    const { error } = await supabase.from("retours").insert({
      source: input.source,
      texte,
      page: input.page?.trim() || null,
      created_by: user.id,
    });
    if (error) return { error: error.message };
    return { ok: true };
  } catch (e) {
    return { error: e instanceof Error ? e.message : "Erreur." };
  }
}

// Marque l'accueil V1 (cinématique de bienvenue) comme joué : ne se rejoue plus.
export async function markWelcomedV1() {
  try {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (!user) return;
    await supabase
      .from("profiles")
      .update({ welcomed_v1_at: new Date().toISOString() })
      .eq("id", user.id);
  } catch {
    // Non critique : au pire la cinématique pourrait se rejouer.
  }
}
