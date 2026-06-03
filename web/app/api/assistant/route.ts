import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { SYSTEM_PROMPT } from "@/lib/assistant/knowledge";
import { tools, executeTool } from "@/lib/assistant/tools";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MODEL = "claude-haiku-4-5";
const MAX_ITERATIONS = 6;
const MAX_TOKENS = 1024;

// Consigne du « point d'ouverture » proactif : Magellan démarre la session en
// faisant le point tout seul et en proposant des actions, au lieu d'attendre.
const BRIEFING_INSTRUCTION = `[DÉMARRAGE DE SESSION] Tu ouvres la session, sois actif et bref.
1. Salue en une ligne.
2. Demande POUR QUEL CLIENT / VERTICALE on travaille aujourd'hui. Utilise lister_cibles pour connaître les verticales existantes et propose-les. Formule comme une vraie proposition (ex: « On reprend pour Rossini Energy ? Si oui je te fais l'état des lieux complet. »).
3. NE déroule PAS encore l'état des lieux ni le plan : attends le choix du client.
Style direct, chaleureux, 2-3 lignes max.
Termine IMPÉRATIVEMENT par une ligne au format exact :
===ACTIONS=== On reprend pour <Verticale A> | On reprend pour <Verticale B> | Vue d'ensemble (tous clients)
en remplaçant par les vraies verticales renvoyées par lister_cibles (max 4 actions). Chaque action est une phrase que je peux te renvoyer telle quelle.`;

// Extrait la ligne ===ACTIONS=== en suggestions cliquables, et la retire du texte.
function parseActions(text: string): { reply: string; suggestions: string[] } {
  const idx = text.lastIndexOf("===ACTIONS===");
  if (idx === -1) return { reply: text, suggestions: [] };
  const reply = text.slice(0, idx).trim();
  const suggestions = text
    .slice(idx + "===ACTIONS===".length)
    .split("|")
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 4);
  return { reply: reply || text, suggestions };
}

type Msg = { role: "user" | "assistant"; content: unknown };

export async function POST(req: NextRequest) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Non authentifié." }, { status: 401 });
  }

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return NextResponse.json({
      reply:
        "⚙️ L'assistant n'est pas encore activé : la clé `ANTHROPIC_API_KEY` manque dans les variables d'environnement Vercel. Ajoute-la dans Vercel → Settings → Environment Variables, puis redéploie.",
    });
  }

  const body = await req.json().catch(() => null);
  const briefing = body?.briefing === true;

  let messages: Msg[];
  if (briefing) {
    // Point d'ouverture proactif : on amorce avec la consigne de briefing.
    messages = [{ role: "user", content: BRIEFING_INSTRUCTION }];
  } else {
    const incoming: unknown[] = Array.isArray(body?.messages) ? body.messages : [];
    messages = incoming
      .filter(
        (m): m is { role: "user" | "assistant"; content: string } =>
          !!m &&
          typeof m === "object" &&
          ((m as Msg).role === "user" || (m as Msg).role === "assistant") &&
          typeof (m as Msg).content === "string",
      )
      .slice(-12)
      .map((m) => ({ role: m.role, content: m.content }));

    if (messages.length === 0) {
      return NextResponse.json({ error: "Message vide." }, { status: 400 });
    }
  }

  try {
    const steps: string[] = [];
    for (let i = 0; i < MAX_ITERATIONS; i++) {
      const res = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-api-key": apiKey,
          "anthropic-version": "2023-06-01",
        },
        body: JSON.stringify({
          model: MODEL,
          max_tokens: MAX_TOKENS,
          system: SYSTEM_PROMPT,
          tools,
          messages,
        }),
      });

      if (!res.ok) {
        const detail = await res.text();
        console.error("Anthropic API error", res.status, detail);
        return NextResponse.json(
          { error: "L'assistant est momentanément indisponible." },
          { status: 502 },
        );
      }

      const data = await res.json();
      const blocks: Array<Record<string, unknown>> = Array.isArray(data.content)
        ? data.content
        : [];
      messages.push({ role: "assistant", content: blocks });

      if (data.stop_reason === "tool_use") {
        const toolResults = [];
        for (const block of blocks) {
          if (block.type === "tool_use") {
            steps.push(block.name as string);
            const result = await executeTool(
              block.name as string,
              (block.input as Record<string, unknown>) ?? {},
              supabase,
            );
            toolResults.push({
              type: "tool_result",
              tool_use_id: block.id,
              content: result,
            });
          }
        }
        messages.push({ role: "user", content: toolResults });
        continue;
      }

      const text = blocks
        .filter((b) => b.type === "text")
        .map((b) => b.text as string)
        .join("\n")
        .trim();
      const { reply, suggestions } = parseActions(text);
      return NextResponse.json({
        reply: reply || "Je n'ai pas de réponse à formuler.",
        steps,
        suggestions,
      });
    }

    return NextResponse.json({
      reply:
        "Désolé, cette demande est trop complexe à traiter d'un coup. Reformule plus simplement.",
    });
  } catch (e) {
    console.error("Assistant error", e);
    return NextResponse.json(
      { error: "Erreur interne de l'assistant." },
      { status: 500 },
    );
  }
}
