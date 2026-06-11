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
  telephone?: string | null;
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
      telephone: input.telephone?.trim() || null,
      deadlines,
      updated_by: user.id,
      updated_at: new Date().toISOString(),
    })
    .eq("id", "main");
  if (error) return { error: error.message };
  revalidatePath("/tableau-de-bord");
  return { ok: true };
}

const TYPE_LABEL: Record<string, string> = {
  cree: "leads créés",
  envoye: "emails envoyés",
  ouvert: "ouvertures",
  repondu: "réponses reçues",
  relance: "relances",
  ecarte: "leads écartés",
  note: "notes/éditions",
  rebond: "rebonds",
};

/**
 * Génère automatiquement le récap « où on en est » (résumé de session) à partir
 * de l'activité récente, et l'écrit dans app_context — alimente la modale
 * d'accueil et le bandeau Reprise. Boucle la reprise au login (charte agent-first).
 */
export async function genererResumeSession() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { error: "Non authentifié." };

  const { data: ctx } = await supabase
    .from("app_context")
    .select("resume_genere_le, client_actif, objectif_final")
    .eq("id", "main")
    .maybeSingle();

  // Activité depuis le dernier récap (ou 2 jours par défaut).
  const since =
    ctx?.resume_genere_le ?? new Date(Date.now() - 2 * 86_400_000).toISOString();

  const [{ data: events }, { count: runsTermines }, { count: veilleNouveaux }] =
    await Promise.all([
      supabase.from("lead_events").select("type").gt("at", since).limit(2000),
      supabase
        .from("runs")
        .select("id", { count: "exact", head: true })
        .eq("status", "termine")
        .gt("updated_at", since),
      supabase
        .from("veille_signaux")
        .select("id", { count: "exact", head: true })
        .eq("statut", "nouveau")
        .gt("created_at", since),
    ]);

  const parType: Record<string, number> = {};
  for (const e of (events as { type: string }[] | null) ?? []) {
    parType[e.type] = (parType[e.type] ?? 0) + 1;
  }
  const faits: string[] = [];
  for (const [type, n] of Object.entries(parType)) {
    if (n > 0) faits.push(`${n} ${TYPE_LABEL[type] ?? type}`);
  }
  if ((runsTermines ?? 0) > 0) faits.push(`${runsTermines} recherche(s) terminée(s)`);
  if ((veilleNouveaux ?? 0) > 0) faits.push(`${veilleNouveaux} nouveau(x) signal(aux) de veille`);

  const nowIso = new Date().toISOString();
  let resume: string;

  if (faits.length === 0) {
    resume = "Rien de nouveau depuis la dernière session.";
  } else {
    const apiKey = process.env.ANTHROPIC_API_KEY;
    const digest = faits.join(", ");
    if (!apiKey) {
      // Repli sans IA : on liste les faits bruts.
      resume = `Depuis la dernière session : ${digest}.`;
    } else {
      try {
        const res = await fetch("https://api.anthropic.com/v1/messages", {
          method: "POST",
          headers: {
            "content-type": "application/json",
            "x-api-key": apiKey,
            "anthropic-version": "2023-06-01",
          },
          body: JSON.stringify({
            model: "claude-sonnet-4-6",
            max_tokens: 200,
            messages: [
              {
                role: "user",
                content: `Tu rédiges le récap « où on en est » pour la reprise au login d'un CRM de prospection B2B${
                  ctx?.client_actif ? ` (client : ${ctx.client_actif})` : ""
                }. Données d'activité depuis la dernière session : ${digest}. Écris UNE à DEUX phrases, ton direct et factuel, en français, sans liste ni préambule.`,
              },
            ],
          }),
        });
        if (res.ok) {
          const data = await res.json();
          const text = (Array.isArray(data.content) ? data.content : [])
            .filter((b: Record<string, unknown>) => b.type === "text")
            .map((b: Record<string, unknown>) => (b.text as string) ?? "")
            .join(" ")
            .trim();
          resume = text || `Depuis la dernière session : ${digest}.`;
        } else {
          resume = `Depuis la dernière session : ${digest}.`;
        }
      } catch {
        resume = `Depuis la dernière session : ${digest}.`;
      }
    }
  }

  const { error } = await supabase
    .from("app_context")
    .update({ resume_session: resume, resume_genere_le: nowIso, updated_by: user.id })
    .eq("id", "main");
  if (error) return { error: error.message };
  revalidatePath("/tableau-de-bord");
  return { ok: true, resume };
}
