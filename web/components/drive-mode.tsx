"use client";

import { useEffect, useRef, useState } from "react";
import { speak, stopSpeaking, ttsSupported } from "@/lib/speech";

// PC — Mode « déplacement » / on-the-go : vue plein écran vocale, mains-libres.
// On parle (mot d'éveil « Magellan » optionnel), Magellan répond à VOIX HAUTE.
// Engagé par l'event `leads:drive` (badge accueil ou commande à l'agent).
//
// PB — Brique vocale conversationnelle : écoute continue (Web Speech) + synthèse
// vocale (speechSynthesis). Le micro est coupé pendant que Magellan parle pour
// éviter le larsen, puis réenclenché automatiquement.

type Status = "off" | "listening" | "thinking" | "speaking";

// Retire un mot d'éveil en tête de phrase (« Magellan, … », « M, … », « OK Magellan »).
const WAKE = /^(ok\s+|hey\s+)?(magellan|magelan|magellane|m)\b[\s,.:!?-]*/i;

const RACCOURCIS = [
  "Mon plan du jour",
  "Les réponses reçues",
  "Mes RDV à venir",
  "Mes relances dues",
];

export function DriveMode() {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<Status>("off");
  const [lastUser, setLastUser] = useState("");
  const [lastReply, setLastReply] = useState("");
  const [interim, setInterim] = useState("");
  const [speechSupported, setSpeechSupported] = useState(false);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recRef = useRef<any>(null);
  const activeRef = useRef(false); // écoute mains-libres engagée
  const busyRef = useRef(false); // en train de réfléchir/parler → micro coupé
  const historyRef = useRef<{ role: "user" | "assistant"; content: string }[]>([]);

  useEffect(() => {
    setSpeechSupported(
      typeof window !== "undefined" &&
        ("SpeechRecognition" in window || "webkitSpeechRecognition" in window),
    );
  }, []);

  useEffect(() => {
    function onDrive() {
      setOpen(true);
    }
    window.addEventListener("leads:drive", onDrive);
    return () => window.removeEventListener("leads:drive", onDrive);
  }, []);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function buildRec(): any {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Ctor =
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!Ctor) return null;
    const rec = new Ctor();
    rec.lang = "fr-FR";
    rec.interimResults = true;
    rec.continuous = true;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    rec.onresult = (e: any) => {
      if (busyRef.current) return;
      let finalTxt = "";
      let inter = "";
      for (let k = e.resultIndex; k < e.results.length; k++) {
        const tr = e.results[k][0].transcript;
        if (e.results[k].isFinal) finalTxt += tr;
        else inter += tr;
      }
      if (inter) setInterim(inter.trim());
      if (finalTxt.trim()) {
        setInterim("");
        handleCommand(finalTxt.trim());
      }
    };
    rec.onend = () => {
      // Chrome coupe après un silence : on relance tant qu'on est en écoute active.
      if (activeRef.current && !busyRef.current) {
        try {
          rec.start();
        } catch {
          /* déjà démarré */
        }
      }
    };
    rec.onerror = () => {
      /* erreurs transitoires ignorées ; onend relancera si besoin */
    };
    return rec;
  }

  function startListening() {
    if (!speechSupported) return;
    if (!recRef.current) recRef.current = buildRec();
    if (!recRef.current) return;
    activeRef.current = true;
    busyRef.current = false;
    setStatus("listening");
    try {
      recRef.current.start();
    } catch {
      /* déjà démarré */
    }
  }

  function stopListening() {
    activeRef.current = false;
    try {
      recRef.current?.stop();
    } catch {
      /* no-op */
    }
    setStatus("off");
  }

  async function handleCommand(raw: string) {
    const cmd = raw.replace(WAKE, "").trim() || raw.trim();
    if (!cmd) return;
    busyRef.current = true;
    try {
      recRef.current?.stop();
    } catch {
      /* no-op */
    }
    setLastUser(cmd);
    setLastReply("");
    setStatus("thinking");
    historyRef.current = [
      ...historyRef.current,
      { role: "user" as const, content: cmd },
    ].slice(-12);

    const reprendre = () => {
      busyRef.current = false;
      if (activeRef.current) {
        setStatus("listening");
        try {
          recRef.current?.start();
        } catch {
          /* déjà démarré */
        }
      } else {
        setStatus("off");
      }
    };

    try {
      const res = await fetch("/api/assistant", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ messages: historyRef.current }),
      });
      const data = await res.json();
      const reply = data.reply ?? data.error ?? "Je n'ai pas pu répondre, réessaie.";
      historyRef.current = [
        ...historyRef.current,
        { role: "assistant" as const, content: reply },
      ].slice(-12);
      setLastReply(reply);
      setStatus("speaking");
      speak(reply, reprendre);
    } catch {
      const err = "Connexion impossible. Réessaie dans un instant.";
      setLastReply(err);
      setStatus("speaking");
      speak(err, reprendre);
    }
  }

  function interrompre() {
    stopSpeaking();
    busyRef.current = false;
    if (activeRef.current) {
      setStatus("listening");
      try {
        recRef.current?.start();
      } catch {
        /* no-op */
      }
    } else {
      setStatus("off");
    }
  }

  function close() {
    stopListening();
    stopSpeaking();
    busyRef.current = false;
    setInterim("");
    setLastUser("");
    setLastReply("");
    historyRef.current = [];
    setStatus("off");
    setOpen(false);
  }

  // Nettoyage au démontage.
  useEffect(
    () => () => {
      try {
        recRef.current?.stop();
      } catch {
        /* no-op */
      }
      stopSpeaking();
    },
    [],
  );

  if (!open) return null;

  const statutLabel: Record<Status, string> = {
    off: "En pause",
    listening: "Je t'écoute…",
    thinking: "Magellan réfléchit…",
    speaking: "Magellan répond…",
  };
  const ecoute = status === "listening";

  return (
    <div className="fixed inset-0 z-[60] flex flex-col bg-gradient-to-b from-[var(--brand)] to-[var(--brand-dark)] text-white">
      {/* En-tête */}
      <div className="flex items-center justify-between px-5 py-4">
        <div className="text-sm font-semibold opacity-90">🚗 Mode déplacement</div>
        <button
          onClick={close}
          aria-label="Quitter le mode déplacement"
          className="rounded-lg bg-white/15 px-3 py-1.5 text-sm font-medium hover:bg-white/25"
        >
          Quitter ×
        </button>
      </div>

      {/* Zone centrale : état + échange */}
      <div className="flex flex-1 flex-col items-center justify-center gap-6 px-6 text-center">
        {!speechSupported ? (
          <p className="max-w-md text-lg">
            La reconnaissance vocale n&apos;est pas disponible sur ce navigateur.
            Utilise Chrome ou Safari sur ton téléphone pour le mode mains-libres.
          </p>
        ) : (
          <>
            <p className="text-sm uppercase tracking-wide opacity-80">
              {statutLabel[status]}
            </p>

            {/* Gros bouton micro : engage / coupe l'écoute mains-libres */}
            <button
              onClick={ecoute || status === "thinking" || status === "speaking" ? stopListening : startListening}
              className={`flex h-40 w-40 items-center justify-center rounded-full border-4 border-white/40 text-6xl shadow-2xl transition ${
                ecoute
                  ? "animate-pulse bg-white/25"
                  : status === "speaking"
                    ? "bg-white/15"
                    : "bg-white/10 hover:bg-white/20"
              }`}
            >
              {status === "speaking" ? "🔊" : "🎙️"}
            </button>

            <p className="min-h-[1.5rem] max-w-xl text-base italic opacity-90">
              {interim || (ecoute ? "Dis « Magellan… » ou pose ta question." : "")}
            </p>

            {/* Dernier échange */}
            {lastUser && (
              <div className="w-full max-w-xl space-y-2 rounded-2xl bg-black/15 p-4 text-left">
                <p className="text-sm opacity-80">🗣️ {lastUser}</p>
                {lastReply && <p className="text-base leading-relaxed">🧭 {lastReply}</p>}
              </div>
            )}

            {status === "speaking" && (
              <button
                onClick={interrompre}
                className="rounded-lg bg-white/20 px-4 py-2 text-sm font-medium hover:bg-white/30"
              >
                ⏹️ Stop
              </button>
            )}

            {/* Raccourcis tapables (sans la voix) */}
            <div className="flex flex-wrap justify-center gap-2 pt-2">
              {RACCOURCIS.map((r) => (
                <button
                  key={r}
                  onClick={() => handleCommand(r)}
                  disabled={status === "thinking"}
                  className="rounded-full bg-white/15 px-3.5 py-1.5 text-sm font-medium hover:bg-white/25 disabled:opacity-40"
                >
                  {r}
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Pied : note */}
      <p className="px-6 pb-5 text-center text-xs opacity-70">
        {ttsSupported()
          ? "Mains-libres : parle, Magellan te répond à voix haute. Reste prudent au volant."
          : "Lecture vocale indisponible sur ce navigateur — les réponses s'afficheront à l'écran."}
      </p>
    </div>
  );
}
