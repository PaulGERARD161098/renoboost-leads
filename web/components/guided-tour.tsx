"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { TOUR_STEPS } from "@/lib/tour";

// PA — Visite guidée interactive, rejouable. Montée globalement (layout app) et
// déclenchée par l'event `leads:tour` (depuis l'accueil, le bouton dédié, ou une
// commande à Magellan « remontre-moi comment marche Leads »).
export function GuidedTour() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [i, setI] = useState(0);

  useEffect(() => {
    function onTour() {
      setI(0);
      setOpen(true);
    }
    window.addEventListener("leads:tour", onTour);
    return () => window.removeEventListener("leads:tour", onTour);
  }, []);

  // Fermeture au clavier (Échap) + navigation flèches.
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
      else if (e.key === "ArrowRight") setI((n) => Math.min(n + 1, TOUR_STEPS.length - 1));
      else if (e.key === "ArrowLeft") setI((n) => Math.max(n - 1, 0));
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (!open) return null;

  const step = TOUR_STEPS[i];
  const dernier = i === TOUR_STEPS.length - 1;

  function allerVoir() {
    setOpen(false);
    router.push(step.href);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <div className="w-full max-w-lg overflow-hidden rounded-2xl border border-[var(--border)] bg-white shadow-2xl">
        {/* En-tête */}
        <div className="flex items-center justify-between bg-[var(--brand)] px-5 py-3 text-white">
          <div className="text-sm font-semibold">🧭 Visite guidée de Leads</div>
          <button
            onClick={() => setOpen(false)}
            aria-label="Fermer la visite"
            className="rounded-md px-2 py-1 text-lg leading-none text-white/90 hover:bg-white/15"
          >
            ×
          </button>
        </div>

        {/* Contenu */}
        <div className="p-6">
          <div className="mb-3 flex items-center gap-3">
            <span className="text-3xl">{step.icon}</span>
            <h2 className="text-lg font-bold">{step.titre}</h2>
          </div>
          <p className="text-sm leading-relaxed text-slate-700">{step.texte}</p>

          {/* Progression (points) */}
          <div className="mt-5 flex flex-wrap gap-1.5">
            {TOUR_STEPS.map((s, j) => (
              <button
                key={s.titre}
                onClick={() => setI(j)}
                aria-label={`Étape ${j + 1} : ${s.titre}`}
                className={`h-2 w-2 rounded-full transition ${
                  j === i ? "bg-[var(--brand)]" : "bg-slate-300 hover:bg-slate-400"
                }`}
              />
            ))}
          </div>
          <p className="mt-2 text-xs text-[var(--muted)]">
            Étape {i + 1} / {TOUR_STEPS.length}
          </p>
        </div>

        {/* Pied : navigation */}
        <div className="flex items-center justify-between gap-2 border-t border-[var(--border)] px-5 py-3">
          <button
            onClick={() => (i === 0 ? setOpen(false) : setI(i - 1))}
            className="rounded-lg px-3 py-1.5 text-sm font-medium text-[var(--muted)] hover:bg-slate-100"
          >
            {i === 0 ? "Passer" : "← Précédent"}
          </button>
          <div className="flex items-center gap-2">
            <button
              onClick={allerVoir}
              className="rounded-lg border border-[var(--brand)] px-3 py-1.5 text-sm font-medium text-[var(--brand)] hover:bg-[var(--brand)]/5"
            >
              Aller voir →
            </button>
            <button
              onClick={() => (dernier ? setOpen(false) : setI(i + 1))}
              className="rounded-lg bg-[var(--brand)] px-4 py-1.5 text-sm font-medium text-white hover:bg-[var(--brand-dark)]"
            >
              {dernier ? "Terminer" : "Suivant"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
