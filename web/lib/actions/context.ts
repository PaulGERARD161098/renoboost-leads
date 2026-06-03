"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import type { Deadline } from "@/lib/database.types";

// Met à jour la couche contexte (objectif final, client actif, deadlines,
// résumé de session) — alimente la reprise au login.
export async function updateAppContext(input: {
  objectif_final: string | null;
  client_actif: string | null;
  resume_session: string | null;
  deadlines: Deadline[];
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { error: "Non authentifié." };

  const deadlines = (input.deadlines ?? [])
    .filter((d) => d.label?.trim() && d.date)
    .map((d) => ({ label: d.label.trim(), date: d.date }));

  const { error } = await supabase
    .from("app_context")
    .update({
      objectif_final: input.objectif_final?.trim() || null,
      client_actif: input.client_actif?.trim() || null,
      resume_session: input.resume_session?.trim() || null,
      deadlines,
      updated_by: user.id,
      updated_at: new Date().toISOString(),
    })
    .eq("id", "main");
  if (error) return { error: error.message };
  revalidatePath("/tableau-de-bord");
  return { ok: true };
}
