"use server";

import { createClient } from "@/lib/supabase/server";

// Journalise une suggestion suivie (clic sur une action recommandée). Best-effort,
// jamais bloquant : alimente la mesure de la valeur (charte point 7).
export async function logSuggestionClick(
  source: string,
  action: string,
  href?: string | null,
) {
  try {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();
    await supabase.from("suggestion_clicks").insert({
      source,
      action,
      href: href ?? null,
      actor: user?.id ?? null,
    });
  } catch {
    // Traçage non critique : on n'interrompt jamais la navigation.
  }
}
