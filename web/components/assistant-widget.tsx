"use client";

import { useState, useRef, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Markdown } from "@/components/markdown";
import { isTourRequest, isDriveRequest, isAnalyseRequest } from "@/lib/tour";
import { parseImprovementNote } from "@/lib/feedback";
import { logRetour } from "@/lib/actions/feedback";
import { speak, stopSpeaking, ttsSupported } from "@/lib/speech";

type Message = { role: "user" | "assistant"; content: string; steps?: string[] };

const SUGGESTIONS = [
  "Lance une recherche pour moi",
  "Livre-moi les résultats de ma dernière recherche",
  "Compare mes 5 meilleurs leads",
  "Quels sont mes meilleurs départements ?",
  "Analyse le potentiel solaire de mon top lead",
  "Par où je commence ?",
];

// Libellés lisibles des outils, pour montrer "où on en est".
const STEP_LABEL: Record<string, string> = {
  contexte: "Contexte (objectif/deadlines)",
  plan_du_jour: "Plan du jour",
  compter_leads: "État des lieux",
  lister_leads: "Lecture des leads",
  detail_lead: "Fiche du lead",
  lister_runs: "Recherches récentes",
  stats_recherches: "Perf. des recherches",
  stats_departements: "Perf. par département",
  meilleures_zones: "Meilleures zones",
  lister_zones_cibles: "Zones enregistrées",
  lister_cibles: "Cibles actives",
  lancer_recherche: "Lancement d'une recherche",
  resultats_recherche: "Résultats d'une recherche",
  statut_agent: "État de l'agent",
  analyser_satellite: "Analyse satellite",
};

export function AssistantWidget() {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  // Actions proposées dynamiquement par le briefing (sinon repli sur SUGGESTIONS).
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [briefingLoading, setBriefingLoading] = useState(false);
  const briefed = useRef(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  // Lecture vocale (TTS) d'une réponse : index du message en cours de lecture.
  const [speakingIdx, setSpeakingIdx] = useState<number | null>(null);

  function toggleSpeak(idx: number, text: string) {
    if (speakingIdx === idx) {
      stopSpeaking();
      setSpeakingIdx(null);
      return;
    }
    setSpeakingIdx(idx);
    speak(text, () => setSpeakingIdx(null));
  }

  // Coupe toute lecture quand on ferme le panneau.
  useEffect(() => {
    if (!open) {
      stopSpeaking();
      setSpeakingIdx(null);
    }
  }, [open]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, loading, briefingLoading]);

  // Point d'ouverture proactif : à la première ouverture, Magellan fait le point
  // tout seul et propose des actions, au lieu de l'écran d'attente.
  async function briefing() {
    if (briefed.current) return;
    briefed.current = true;
    setBriefingLoading(true);
    try {
      const res = await fetch("/api/assistant", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ briefing: true }),
      });
      const data = await res.json();
      if (data.reply) {
        setMessages((m) => [
          ...m,
          { role: "assistant", content: data.reply, steps: data.steps },
        ]);
        if (Array.isArray(data.suggestions) && data.suggestions.length)
          setSuggestions(data.suggestions);
      }
    } catch {
      /* en cas d'échec, on retombe sur l'écran d'accueil classique */
      briefed.current = false;
    } finally {
      setBriefingLoading(false);
    }
  }

  // Déclenche le briefing dès qu'on ouvre le panneau pour la première fois.
  useEffect(() => {
    if (open && !briefed.current && messages.length === 0) briefing();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Pont avec la commande vocale de l'accueil (event `magellan:ask`) : on ouvre le
  // panneau et, si une demande est fournie, on l'envoie directement. Un ref garde
  // `send` à jour sans recréer l'écouteur.
  const sendRef = useRef<(t: string) => void>(() => {});
  useEffect(() => {
    function onAsk(e: Event) {
      const question = (e as CustomEvent<string>).detail?.trim();
      setOpen(true);
      if (question) sendRef.current(question);
    }
    window.addEventListener("magellan:ask", onAsk as EventListener);
    return () => window.removeEventListener("magellan:ask", onAsk as EventListener);
  }, []);

  // Dictée vocale (API navigateur Web Speech) : on parle, ça remplit le champ.
  const [listening, setListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    setSpeechSupported(
      typeof window !== "undefined" &&
        ("SpeechRecognition" in window || "webkitSpeechRecognition" in window),
    );
  }, []);

  function toggleMic() {
    if (listening) {
      recognitionRef.current?.stop();
      return;
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Ctor = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!Ctor) return;
    const rec = new Ctor();
    rec.lang = "fr-FR";
    rec.interimResults = true;
    rec.continuous = false;
    let finalText = "";
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    rec.onresult = (e: any) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const tr = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalText += tr;
        else interim += tr;
      }
      setInput((finalText + interim).trim());
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recognitionRef.current = rec;
    setListening(true);
    rec.start();
  }

  async function send(text: string) {
    const content = text.trim();
    if (!content || loading) return;

    // Commandes à l'agent court-circuitées localement : visite guidée / mode déplacement.
    if (isTourRequest(content)) {
      window.dispatchEvent(new CustomEvent("leads:tour"));
      setInput("");
      setMessages((m) => [
        ...m,
        { role: "user", content },
        { role: "assistant", content: "🧭 C'est parti pour la visite guidée de Leads !" },
      ]);
      return;
    }
    if (isDriveRequest(content)) {
      window.dispatchEvent(new CustomEvent("leads:drive"));
      setInput("");
      setMessages((m) => [
        ...m,
        { role: "user", content },
        { role: "assistant", content: "🚗 J'ouvre le mode déplacement, mains-libres." },
      ]);
      return;
    }
    if (isAnalyseRequest(content)) {
      setInput("");
      setMessages((m) => [
        ...m,
        { role: "user", content },
        { role: "assistant", content: "🛰️ J'ouvre l'analyse satellite — dépose une capture ou capture la vue GMaps." },
      ]);
      router.push("/analyse");
      return;
    }

    // Note d'amélioration adressée à Magellan → file `retours` (remontée à Paul +
    // Claude, jamais appliquée sans son OK). Court-circuite l'appel au modèle.
    const note = parseImprovementNote(content);
    if (note) {
      setInput("");
      setMessages((m) => [...m, { role: "user", content }]);
      void logRetour({ source: "magellan", texte: note, page: pathname });
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content:
            "📝 Noté, je le remonte à **Paul & Claude**. Aucun changement ne sera fait sans la validation de Paul : il verra ce que ça change et tranchera. 👍",
        },
      ]);
      return;
    }

    const next = [...messages, { role: "user" as const, content }];
    setMessages(next);
    setInput("");
    setLoading(true);
    try {
      const res = await fetch("/api/assistant", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ messages: next }),
      });
      const data = await res.json();
      const reply =
        data.reply ??
        data.error ??
        "Une erreur est survenue. Réessaie dans un instant.";
      setMessages((m) => [
        ...m,
        { role: "assistant", content: reply, steps: data.steps },
      ]);
      if (Array.isArray(data.suggestions) && data.suggestions.length)
        setSuggestions(data.suggestions);
    } catch {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: "Connexion impossible. Vérifie ta connexion et réessaie.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }
  // Toujours pointer vers la dernière version de `send` pour le pont `magellan:ask`.
  sendRef.current = send;

  return (
    <>
      {/* Bouton flottant */}
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Magellan — assistant de navigation"
        className="fixed bottom-5 right-5 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-[var(--brand)] text-2xl text-white shadow-lg transition hover:scale-105"
      >
        {open ? <span className="leading-none">×</span> : <span>🧭</span>}
      </button>

      {/* Panneau */}
      {open && (
        <div className="fixed bottom-24 right-5 z-40 flex h-[40rem] max-h-[calc(100vh-7rem)] w-[34rem] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-2xl border border-[var(--border)] bg-white shadow-2xl">
          <header className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--brand)] px-4 py-3 text-white">
            <div>
              <div className="font-semibold">🧭 Magellan</div>
              <div className="text-xs opacity-80">
                Votre assistant de navigation commerciale
              </div>
            </div>
            {messages.length > 0 && (
              <button
                onClick={() => {
                  setMessages([]);
                  setSuggestions([]);
                  briefed.current = false;
                }}
                className="rounded-md px-2 py-1 text-xs text-white/90 hover:bg-white/15"
              >
                Effacer
              </button>
            )}
          </header>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
            {messages.length === 0 && !briefingLoading && (
              <div className="space-y-3">
                <p className="text-sm text-[var(--muted)]">
                  Pose-moi une question sur l&apos;outil ou tes prospects.
                </p>
                <div className="flex flex-wrap gap-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      className="rounded-full border border-[var(--border)] px-3 py-1 text-xs text-[var(--muted)] hover:bg-slate-100"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={m.role === "user" ? "text-right" : "text-left"}
              >
                <div
                  className={`inline-block max-w-[88%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                    m.role === "user"
                      ? "whitespace-pre-wrap bg-[var(--brand)] text-white"
                      : "bg-slate-100 text-slate-800"
                  }`}
                >
                  {m.role === "user" ? m.content : <Markdown text={m.content} />}
                </div>
                {m.role === "assistant" && m.steps && m.steps.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {m.steps.map((s, j) => (
                      <span
                        key={j}
                        className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] text-[var(--muted)]"
                      >
                        🔧 {STEP_LABEL[s] ?? s}
                      </span>
                    ))}
                  </div>
                )}
                {m.role === "assistant" && ttsSupported() && (
                  <button
                    onClick={() => toggleSpeak(i, m.content)}
                    className="mt-1 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] text-[var(--muted)] hover:bg-slate-100"
                    title={speakingIdx === i ? "Arrêter la lecture" : "Lire à voix haute"}
                  >
                    {speakingIdx === i ? "⏹️ Stop" : "🔊 Lire"}
                  </button>
                )}
              </div>
            ))}
            {(loading || briefingLoading) && (
              <div className="text-left">
                <div className="inline-flex items-center gap-2 rounded-2xl bg-slate-100 px-3.5 py-2.5 text-sm text-[var(--muted)]">
                  <span className="flex gap-1">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--brand)] [animation-delay:-0.3s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--brand)] [animation-delay:-0.15s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--brand)]" />
                  </span>
                  {briefingLoading
                    ? "Magellan prépare ton point d’ouverture…"
                    : "Magellan travaille…"}
                </div>
              </div>
            )}

            {/* Actions proposées par le briefing : cliquables comme des raccourcis. */}
            {!loading && !briefingLoading && suggestions.length > 0 && (
              <div className="flex flex-wrap gap-2 pt-1">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="rounded-full border border-[var(--brand)] bg-[var(--brand)]/5 px-3 py-1 text-xs font-medium text-[var(--brand)] hover:bg-[var(--brand)]/10"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex items-center gap-2 border-t border-[var(--border)] p-3"
          >
            {speechSupported && (
              <button
                type="button"
                onClick={toggleMic}
                aria-label={listening ? "Arrêter la dictée" : "Dicter à la voix"}
                title={listening ? "Arrêter la dictée" : "Parler à Magellan"}
                className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border text-base transition ${
                  listening
                    ? "animate-pulse border-red-400 bg-red-50 text-red-600"
                    : "border-[var(--border)] text-[var(--muted)] hover:bg-slate-50"
                }`}
              >
                🎙️
              </button>
            )}
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={listening ? "Parle…" : "Écris ta question…"}
              className="flex-1 rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
            >
              Envoyer
            </button>
          </form>
        </div>
      )}
    </>
  );
}
