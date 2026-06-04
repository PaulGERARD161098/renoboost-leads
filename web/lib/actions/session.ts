"use server";

import { createClient } from "@/lib/supabase/server";

// Marque la session courante comme « vue » : horodate la dernière connexion de
// l'utilisateur. La modale d'accueil ne se réaffichera plus jusqu'au lendemain.
export async function markSessionSeen() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return;

  await supabase
    .from("profiles")
    .update({ last_seen_at: new Date().toISOString() })
    .eq("id", user.id);
}
