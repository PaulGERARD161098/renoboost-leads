import { createClient } from "@/lib/supabase/server";
import type { WorkerHeartbeat } from "@/lib/database.types";

// Même seuil que worker-status : au-delà, le worker est considéré hors-ligne et
// l'état de ses clés n'est plus fiable.
const STALE_MS = 60_000;

type KeyDef = { id: string; label: string; role: string; required: boolean };

// Clés portées par le WORKER (Railway) — celles de la génération.
const WORKER_KEYS: KeyDef[] = [
  { id: "google_places", label: "Google Places", role: "découverte des établissements (étage 1)", required: true },
  { id: "anthropic", label: "Anthropic (Claude)", role: "scoring & rédaction (étage 4)", required: true },
  { id: "pappers", label: "Pappers", role: "dirigeant & SIREN — améliore les taux", required: false },
  { id: "dropcontact", label: "Dropcontact", role: "email vérifié — améliore les taux", required: false },
];

/**
 * Panneau « clés API » (charte agent-first : savoir ce qui est prêt AVANT de
 * lancer un run réel). Les clés de génération vivent sur le worker (Railway) :
 * il en rapporte la PRÉSENCE dans son heartbeat. Les clés côté app (Vercel)
 * sont lues directement de l'environnement serveur.
 */
export async function KeysPanel() {
  const supabase = await createClient();
  const { data } = await supabase
    .from("worker_heartbeat")
    .select("mode, last_seen_at, keys")
    .eq("id", "main")
    .maybeSingle();
  const hb = data as Pick<WorkerHeartbeat, "mode" | "last_seen_at" | "keys"> | null;

  const workerStale =
    !hb?.last_seen_at || Date.now() - new Date(hb.last_seen_at).getTime() > STALE_MS;
  const wk = hb?.keys ?? {};
  // Le worker rapporte ses clés depuis un build récent ; un objet vide = worker
  // pas encore à jour, à distinguer d'une clé réellement absente.
  const keysReported = Object.keys(wk).length > 0;

  // Clés côté app (Vercel) — lecture serveur, présence uniquement.
  const webAnthropic = !!process.env.ANTHROPIC_API_KEY;
  const webInstantly = !!process.env.INSTANTLY_API_KEY;

  const requisOk = !workerStale && keysReported && !!wk.google_places && !!wk.anthropic;

  let verdict: { tone: "green" | "amber" | "red" | "gray"; texte: string };
  if (workerStale) {
    verdict = { tone: "gray", texte: "Worker hors-ligne — état des clés inconnu." };
  } else if (!keysReported) {
    verdict = {
      tone: "amber",
      texte: "Worker en ligne, clés pas encore rapportées — redéploie-le pour le détail.",
    };
  } else if (!requisOk) {
    verdict = { tone: "red", texte: "Clé(s) requise(s) manquante(s) — la génération réelle échouera." };
  } else if (hb?.mode !== "real") {
    verdict = { tone: "amber", texte: "Mode démo — la génération réelle est désactivée (WORKER_MODE=real)." };
  } else {
    verdict = { tone: "green", texte: "Prêt pour la vraie génération." };
  }

  const dot: Record<string, string> = {
    green: "bg-emerald-500",
    amber: "bg-amber-500",
    red: "bg-red-500",
    gray: "bg-slate-400",
  };

  return (
    <details className="rounded-xl border border-[var(--border)] bg-white open:shadow-sm">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-2.5 text-sm">
        <span className={`h-2 w-2 shrink-0 rounded-full ${dot[verdict.tone]}`} />
        <span className="font-medium">Clés API</span>
        <span className="text-[var(--muted)]">— {verdict.texte}</span>
        <span className="ml-auto text-xs text-[var(--muted)]">détails ▾</span>
      </summary>

      <div className="space-y-4 border-t border-[var(--border)] px-4 py-3">
        <div>
          <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            Moteur de génération (worker · Railway)
          </div>
          {workerStale ? (
            <p className="text-sm text-[var(--muted)]">
              Worker hors-ligne : impossible de connaître l&apos;état des clés. Redéploie-le sur
              Railway.
            </p>
          ) : !keysReported ? (
            <p className="text-sm text-[var(--muted)]">
              Worker en ligne mais sur un build qui ne rapporte pas encore l&apos;état des clés —
              redéploie-le pour voir le détail ci-dessous.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {WORKER_KEYS.map((k) => (
                <KeyRow key={k.id} def={k} present={!!wk[k.id]} />
              ))}
            </ul>
          )}
        </div>

        <div>
          <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            Application (Vercel)
          </div>
          <ul className="space-y-1.5">
            <KeyRow
              def={{
                id: "web_anthropic",
                label: "Anthropic (app)",
                role: "assistant Magellan & brouillons de réponse",
                required: false,
              }}
              present={webAnthropic}
            />
            <KeyRow
              def={{
                id: "web_instantly",
                label: "Instantly",
                role: "envoi réel des emails (sinon simulation)",
                required: false,
              }}
              present={webInstantly}
            />
          </ul>
        </div>
      </div>
    </details>
  );
}

function KeyRow({ def, present }: { def: KeyDef; present: boolean }) {
  return (
    <li className="flex items-start gap-2 text-sm">
      <span className="mt-0.5 shrink-0">{present ? "✅" : def.required ? "🔴" : "⚪"}</span>
      <span className="min-w-0">
        <span className="font-medium">{def.label}</span>
        {def.required && !present && (
          <span className="ml-1 rounded bg-red-50 px-1 text-xs font-medium text-red-700">requise</span>
        )}
        {!def.required && (
          <span className="ml-1 text-xs text-[var(--muted)]">(optionnel)</span>
        )}
        <span className="block text-xs text-[var(--muted)]">{def.role}</span>
      </span>
    </li>
  );
}
