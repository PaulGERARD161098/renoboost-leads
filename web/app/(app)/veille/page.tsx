import { createClient } from "@/lib/supabase/server";
import type { VeilleSignal } from "@/lib/database.types";
import { VeilleList } from "@/components/veille-list";

export const dynamic = "force-dynamic";

export default async function VeillePage() {
  const supabase = await createClient();
  const { data } = await supabase
    .from("veille_signaux")
    .select("*")
    .in("statut", ["nouveau", "retenu", "converti"])
    .order("created_at", { ascending: false })
    .limit(100);

  const signaux = ((data as VeilleSignal[] | null) ?? []).sort(
    (a, b) =>
      (b.score_intention ?? 0) + (b.score_fit ?? 0) -
      ((a.score_intention ?? 0) + (a.score_fit ?? 0)),
  );

  return (
    <div className="max-w-3xl">
      <h1 className="mb-1 text-2xl font-bold">Veille</h1>
      <p className="mb-5 text-sm text-[var(--muted)]">
        Signaux d&apos;intention détectés sur le web (flotte VE, ombrières,
        électrification) sur le périmètre des cibles — triés par intention × fit.
      </p>
      <VeilleList signaux={signaux} />
    </div>
  );
}
