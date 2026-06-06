import { createClient } from "@/lib/supabase/server";
import type { WorkerHeartbeat } from "@/lib/database.types";

// Au-delà de ce délai sans battement de cœur, le worker est considéré silencieux.
// Le worker poll toutes les ~5 s et écrit un heartbeat à chaque tour ; 60 s
// d'écart signifie clairement un process à l'arrêt (crash, redéploiement long,
// variables manquantes).
const STALE_MS = 60_000;

function ago(iso: string): string {
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `il y a ${s} s`;
  const m = Math.round(s / 60);
  if (m < 60) return `il y a ${m} min`;
  const h = Math.round(m / 60);
  if (h < 24) return `il y a ${h} h`;
  return `il y a ${Math.round(h / 24)} j`;
}

/**
 * Pastille d'état du worker M3 (charte agent-first : « voir le worker vivant
 * sans passer par un dev »). Lit le heartbeat + le nombre de runs en file, et
 * alerte si le process est silencieux alors que des recherches attendent.
 * Composant serveur autonome : à poser sur la page recherche et l'accueil.
 */
export async function WorkerStatus() {
  const supabase = await createClient();
  const [{ data: hbData }, { count: enAttente }] = await Promise.all([
    supabase.from("worker_heartbeat").select("*").eq("id", "main").maybeSingle(),
    supabase.from("runs").select("id", { count: "exact", head: true }).eq("status", "demande"),
  ]);
  const hb = hbData as WorkerHeartbeat | null;
  const pending = enAttente ?? 0;
  const lastSeen = hb?.last_seen_at ?? null;
  const stale = !lastSeen || Date.now() - new Date(lastSeen).getTime() > STALE_MS;

  // Jamais vu : worker probablement pas (re)déployé.
  if (!lastSeen) {
    return (
      <Pill tone="gray">
        <Dot tone="gray" />
        <span>
          <strong>Worker jamais vu</strong> — vérifie le déploiement sur Railway.
        </span>
      </Pill>
    );
  }

  if (stale) {
    return (
      <Pill tone={pending > 0 ? "red" : "amber"}>
        <Dot tone={pending > 0 ? "red" : "amber"} />
        <span>
          {pending > 0 ? (
            <>
              <strong>Worker à l&apos;arrêt</strong> — {pending} recherche
              {pending > 1 ? "s" : ""} en attente non traitée{pending > 1 ? "s" : ""}. Vérifie
              Railway.
            </>
          ) : (
            <>
              <strong>Worker silencieux</strong> ({ago(lastSeen)}) — rien en file pour l&apos;instant.
            </>
          )}
        </span>
      </Pill>
    );
  }

  // Actif.
  return (
    <Pill tone="green">
      <Dot tone="green" pulse />
      <span>
        <strong>Worker actif</strong>
        {hb?.mode ? ` · ${hb.mode === "real" ? "réel" : "démo"}` : ""}
        {hb?.version ? ` · build ${hb.version}` : ""} · {ago(lastSeen)}
        {pending > 0 ? ` · ${pending} en file` : ""}
        {hb?.last_error ? (
          <span className="ml-1 text-amber-700">
            · dernier échec : {hb.last_error.slice(0, 80)}
          </span>
        ) : null}
      </span>
    </Pill>
  );
}

const TONES: Record<string, { box: string; text: string; dot: string }> = {
  green: { box: "border-emerald-200 bg-emerald-50", text: "text-emerald-800", dot: "bg-emerald-500" },
  amber: { box: "border-amber-200 bg-amber-50", text: "text-amber-800", dot: "bg-amber-500" },
  red: { box: "border-red-200 bg-red-50", text: "text-red-800", dot: "bg-red-500" },
  gray: { box: "border-[var(--border)] bg-slate-50", text: "text-slate-600", dot: "bg-slate-400" },
};

function Pill({ tone, children }: { tone: keyof typeof TONES; children: React.ReactNode }) {
  const t = TONES[tone];
  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs ${t.box} ${t.text}`}
    >
      {children}
    </div>
  );
}

function Dot({ tone, pulse = false }: { tone: keyof typeof TONES; pulse?: boolean }) {
  return (
    <span className="relative flex h-2 w-2 shrink-0">
      {pulse && (
        <span
          className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${TONES[tone].dot}`}
        />
      )}
      <span className={`relative inline-flex h-2 w-2 rounded-full ${TONES[tone].dot}`} />
    </span>
  );
}
