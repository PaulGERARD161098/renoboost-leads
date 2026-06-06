"use client";

// Accès rapides sur l'accueil : badge « Mode déplacement » (vue vocale mains-libres,
// PC) et « Visite guidée » (tuto interactif, PA). Dispatchent les events globaux
// écoutés par DriveMode / GuidedTour (montés dans le layout app).
export function HomeModes() {
  return (
    <div className="mb-5 flex flex-wrap gap-2">
      <button
        onClick={() => window.dispatchEvent(new CustomEvent("leads:drive"))}
        className="inline-flex items-center gap-2 rounded-full border border-[var(--brand)] bg-[var(--brand)]/5 px-4 py-2 text-sm font-medium text-[var(--brand)] transition hover:bg-[var(--brand)]/10"
        title="Vue vocale mains-libres pour la voiture / les déplacements"
      >
        🚗 Mode déplacement
      </button>
      <button
        onClick={() => window.dispatchEvent(new CustomEvent("leads:tour"))}
        className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-white px-4 py-2 text-sm font-medium text-[var(--muted)] transition hover:bg-slate-50"
        title="Revoir la prise en main de Leads, écran par écran"
      >
        🧭 Visite guidée
      </button>
    </div>
  );
}
