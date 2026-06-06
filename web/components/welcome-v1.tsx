"use client";

import { useEffect, useRef, useState } from "react";
import { Markdown } from "@/components/markdown";
import { markWelcomedV1 } from "@/lib/actions/feedback";
import { speak, stopSpeaking, ttsSupported } from "@/lib/speech";
import {
  WELCOME_V1_SLIDES,
  WELCOME_V1_TITLE,
  WELCOME_V1_TOTAL_MS,
} from "@/lib/welcome-v1";

// Accueil « V1 en ligne » d'Henry : une cinématique scriptée (~20 s) qui se joue
// UNE seule fois (gated côté layout par profiles.welcomed_v1_at), skippable.
// À la fin, elle active le pop-up de retours qui suivra Henry partout.
export function WelcomeV1() {
  const [i, setI] = useState(0);
  const [done, setDone] = useState(false);
  const [voiceOn, setVoiceOn] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Marquage « vu » fait une seule fois, même si on skippe pendant la lecture.
  const marked = useRef(false);

  function mark() {
    if (marked.current) return;
    marked.current = true;
    void markWelcomedV1();
  }

  // Termine la cinématique : on horodate, on coupe la voix, et on amorce le
  // pop-up de retours (il prendra le relais et suivra Henry sur toutes les pages).
  function finish() {
    mark();
    stopSpeaking();
    if (timerRef.current) clearTimeout(timerRef.current);
    try {
      localStorage.setItem("leads_henry_retour", "open");
    } catch {
      /* localStorage indisponible : le dock retombera sur son défaut */
    }
    window.dispatchEvent(new CustomEvent("leads:retour-open"));
    setDone(true);
  }

  // Déroulé auto des slides ; à la dernière, on attend sa durée puis on termine.
  useEffect(() => {
    if (done) return;
    const slide = WELCOME_V1_SLIDES[i];
    timerRef.current = setTimeout(() => {
      if (i < WELCOME_V1_SLIDES.length - 1) setI((n) => n + 1);
      else finish();
    }, slide.duree);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [i, done]);

  // Voix off optionnelle : lit la slide courante quand l'option est active.
  useEffect(() => {
    if (done || !voiceOn) return;
    speak(WELCOME_V1_SLIDES[i].voix);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [i, voiceOn, done]);

  useEffect(() => () => stopSpeaking(), []);

  if (done) return null;

  const slide = WELCOME_V1_SLIDES[i];
  const elapsedBefore = WELCOME_V1_SLIDES.slice(0, i).reduce(
    (s, x) => s + x.duree,
    0,
  );
  const pct = Math.min(
    100,
    Math.round(((elapsedBefore + slide.duree) / WELCOME_V1_TOTAL_MS) * 100),
  );

  function toggleVoice() {
    setVoiceOn((v) => {
      const next = !v;
      if (!next) stopSpeaking();
      else speak(WELCOME_V1_SLIDES[i].voix);
      return next;
    });
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
      <div className="w-full max-w-2xl overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-slate-900 to-slate-800 text-white shadow-2xl">
        {/* Titre */}
        <div className="border-b border-white/10 bg-white/5 px-7 py-5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--brand)]">
            🎬 Leads — V1
          </p>
          <h1 className="mt-1 text-xl font-bold leading-snug sm:text-2xl">
            {WELCOME_V1_TITLE}
          </h1>
        </div>

        {/* Scène */}
        <div className="flex min-h-[15rem] flex-col items-center justify-center px-8 py-10 text-center">
          <div key={i} className="animate-[fadeIn_0.5s_ease]">
            <div className="mb-4 text-6xl">{slide.icon}</div>
            <div className="mx-auto max-w-lg text-lg leading-relaxed text-slate-100">
              <Markdown text={slide.texte} />
            </div>
          </div>
        </div>

        {/* Progression + commandes */}
        <div className="space-y-3 border-t border-white/10 px-7 py-4">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full rounded-full bg-[var(--brand)] transition-all duration-500 ease-linear"
              style={{ width: `${pct}%` }}
            />
          </div>
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5">
              {WELCOME_V1_SLIDES.map((s, j) => (
                <span
                  key={j}
                  className={`h-1.5 w-1.5 rounded-full transition ${
                    j <= i ? "bg-[var(--brand)]" : "bg-white/20"
                  }`}
                />
              ))}
            </div>
            <div className="flex items-center gap-2">
              {ttsSupported() && (
                <button
                  onClick={toggleVoice}
                  className="rounded-lg px-3 py-1.5 text-xs font-medium text-white/80 hover:bg-white/10"
                  title={voiceOn ? "Couper la voix" : "Activer la voix off"}
                >
                  {voiceOn ? "🔊 Voix" : "🔇 Voix"}
                </button>
              )}
              <button
                onClick={finish}
                className="rounded-lg bg-[var(--brand)] px-4 py-1.5 text-sm font-semibold text-white hover:opacity-90"
              >
                {i === WELCOME_V1_SLIDES.length - 1 ? "C'est parti →" : "Passer"}
              </button>
            </div>
          </div>
        </div>
      </div>

      <style>{`@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}`}</style>
    </div>
  );
}
