"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";

export async function createRun(input: {
  verticaleId: string;
  departement: string;
  effectifMin?: number | null;
  budgetEur?: number | null;
  volumeCible?: number | null;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { data, error } = await supabase
    .from("runs")
    .insert({
      verticale_id: input.verticaleId,
      zone: { departement: input.departement, effectif_min: input.effectifMin ?? null },
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
