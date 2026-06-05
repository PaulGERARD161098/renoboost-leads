"use client";

import { useEffect, useRef, useState } from "react";

// Barre de commande de l'accueil : on écrit OU on parle (Web Speech, fr-FR), et la
// demande est transmise à Magellan (assistant-widget) via un event window
// `magellan:ask`. Permet d'orienter le travail très vite, à la voix.
//
// Bonus : délègue aussi les clics sur tout [data-magellan-open] (ex. bloc
// « Autre chose ? ») pour ouvrir Magellan sans demande pré-remplie.
export function HomeCommand() {
  const [text, setText] = useState("");
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

  // Ouvre Magellan (panneau de droite) avec une demande optionnelle.
  function ask(question?: string) {
    window.dispatchEvent(
      new CustomEvent("magellan:ask", { detail: question?.trim() ?? "" }),
    );
  }

  // Délégation : un clic sur un bloc marqué [data-magellan-open] ouvre Magellan.
  useEffect(() => {
    function onClick(e: MouseEvent) {
      const el = (e.target as HTMLElement)?.closest("[data-magellan-open]");
      if (el) ask();
    }
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const v = text.trim();
    if (!v) return;
    ask(v);
    setText("");
  }

  function toggleMic() {
    if (listening) {
      recognitionRef.current?.stop();
      return;
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Ctor =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!Ctor) return;
    const rec = new Ctor();
    rec.lang = "fr-FR";
    rec.interimResults = true;
    rec.continuous = false;
    let finalText = "";
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    rec.onresult = (ev: any) => {
      let interim = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const tr = ev.results[i][0].transcript;
        if (ev.results[i].isFinal) finalText += tr;
        else interim += tr;
      }
      setText((finalText + interim).trim());
    };
    // À la fin de la dictée, si on a capté quelque chose, on l'envoie direct.
    rec.onend = () => {
      setListening(false);
      const v = finalText.trim();
      if (v) {
        ask(v);
        setText("");
      }
    };
    rec.onerror = () => setListening(false);
    recognitionRef.current = rec;
    setListening(true);
    rec.start();
  }

  return (
    <form
      onSubmit={submit}
      className="flex items-center gap-2 rounded-2xl border border-[var(--border)] bg-white p-2 shadow-sm focus-within:border-[var(--brand)]"
    >
      {speechSupported && (
        <button
          type="button"
          onClick={toggleMic}
          aria-label={listening ? "Arrêter la dictée" : "Parler à Magellan"}
          title={listening ? "Arrêter la dictée" : "Parler à Magellan"}
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border text-lg transition ${
            listening
              ? "animate-pulse border-red-400 bg-red-50 text-red-600"
              : "border-[var(--border)] text-[var(--muted)] hover:bg-slate-50"
          }`}
        >
          🎙️
        </button>
      )}
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={
          listening
            ? "Parle… (ex. « montre mes meilleurs leads solaires »)"
            : "Demande à Magellan d'orienter ton travail…"
        }
        className="flex-1 bg-transparent px-2 text-sm outline-none"
      />
      <button
        type="submit"
        disabled={!text.trim()}
        className="rounded-xl bg-[var(--brand)] px-4 py-2.5 text-sm font-medium text-white transition hover:bg-[var(--brand-dark)] disabled:opacity-40"
      >
        Demander
      </button>
    </form>
  );
}
