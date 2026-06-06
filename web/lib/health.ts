import { createClient } from "@/lib/supabase/server";
import type { SystemSeverite, SystemStatus, WorkerHeartbeat } from "@/lib/database.types";

export type SystemHealth = { severite: SystemSeverite; message: string | null };

const RANK: Record<SystemSeverite, number> = { ok: 0, warning: 1, critical: 2 };

// Au-delà de ce délai sans heartbeat, le worker est considéré à l'arrêt (cf.
// worker-status.tsx — même seuil).
const WORKER_STALE_MS = 60_000;

/**
 * Santé globale calculée côté serveur (le « pire » l'emporte) :
 *  - joignabilité Supabase : si la requête échoue → critical ;
 *  - incident déclaré dans system_status (crash / attaque / sécurité) ;
 *  - worker à l'arrêt avec des recherches en attente → warning.
 *
 * La perte de connexion *du navigateur* (hors-ligne) est détectée côté client
 * (HealthName / LoginHealthBanner), pas ici.
 */
export async function getSystemHealth(): Promise<SystemHealth> {
  const supabase = await createClient();
  let severite: SystemSeverite = "ok";
  let message: string | null = null;
  const promote = (s: SystemSeverite, m: string | null) => {
    if (RANK[s] > RANK[severite]) {
      severite = s;
      message = m;
    }
  };

  // Incident déclaré + test implicite de joignabilité Supabase (la requête).
  const { data, error } = await supabase
    .from("system_status")
    .select("severite, message")
    .eq("id", "main")
    .maybeSingle();
  if (error) {
    return { severite: "critical", message: "Connexion à la base de données indisponible." };
  }
  const st = data as Pick<SystemStatus, "severite" | "message"> | null;
  if (st && st.severite !== "ok") {
    promote(st.severite, st.message ?? "Incident en cours.");
  }

  // Worker à l'arrêt alors que des recherches attendent → dégradé (sans écraser
  // un incident critical déclaré).
  const { data: hbData } = await supabase
    .from("worker_heartbeat")
    .select("last_seen_at, pending_runs")
    .eq("id", "main")
    .maybeSingle();
  const hb = hbData as Pick<WorkerHeartbeat, "last_seen_at" | "pending_runs"> | null;
  if (hb?.last_seen_at) {
    const stale = Date.now() - new Date(hb.last_seen_at).getTime() > WORKER_STALE_MS;
    if (stale && (hb.pending_runs ?? 0) > 0) {
      promote("warning", "Le worker semble à l'arrêt alors que des recherches attendent.");
    }
  }

  return { severite, message };
}
