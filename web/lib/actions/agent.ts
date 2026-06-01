"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";

export async function updateAgentConfig(input: {
  id: string;
  autonomie: boolean;
  cibles_autorisees: string[];
  departements: string[];
  budget_jour_eur: number;
  budget_run_eur: number;
  volume_run: number;
  effectif_min: number | null;
  max_runs_jour: number;
  cadence_min: number;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { error } = await supabase
    .from("agent_config")
    .update({
      autonomie: input.autonomie,
      cibles_autorisees: input.cibles_autorisees,
      departements: input.departements,
      budget_jour_eur: input.budget_jour_eur,
      budget_run_eur: input.budget_run_eur,
      volume_run: input.volume_run,
      effectif_min: input.effectif_min,
      max_runs_jour: input.max_runs_jour,
      cadence_min: input.cadence_min,
      updated_by: user?.id ?? null,
      updated_at: new Date().toISOString(),
    })
    .eq("id", input.id);

  if (error) return { error: error.message };
  revalidatePath("/agent");
  return { ok: true };
}
