"use client";

import { useState } from "react";

// Accès rapide « déjà équipé en bornes ? » : deux boutons qui ouvrent les cartes
// Chargemap (bornes publiques) et Rossini Energy (installations RE), + l'adresse
// du prospect à rechercher (copiable). Pas d'ingestion de données : simple lien.
export function BornesLinks({
  adresse,
  ville,
  codePostal,
  irve,
}: {
  adresse: string | null;
  ville: string | null;
  codePostal: string | null;
  // Synthèse IRVE (bornes publiques) calculée si le lead est géolocalisé.
  irve?: { rayon: number; rayonKm: number; surSite: number; plusProcheKm: number | null } | null;
}) {
  const [copie, setCopie] = useState(false);
  const adresseComplete = [adresse, codePostal, ville].filter(Boolean).join(" ").trim();

  function copier() {
    if (!adresseComplete) return;
    navigator.clipboard?.writeText(adresseComplete).then(() => {
      setCopie(true);
      setTimeout(() => setCopie(false), 1500);
    });
  }

  return (
    <div className="rounded-xl border border-[var(--border)] bg-white p-5">
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
        Déjà équipé en bornes ?
      </h2>
      <p className="mb-3 text-sm text-[var(--muted)]">
        Vérifie sur les cartes si ce prospect (ou un voisin) a déjà une borne.
        {adresseComplete ? " Recherche l’adresse ci-dessous sur la carte ouverte." : ""}
      </p>

      {irve && (
        <div className="mb-3 rounded-lg bg-slate-50 px-3 py-2 text-sm">
          {irve.surSite > 0 ? (
            <span className="font-medium text-amber-700">
              ⚡ Borne publique sur site — probablement déjà équipé.
            </span>
          ) : irve.rayon > 0 ? (
            <span className="text-slate-700">
              ⚡ {irve.rayon} borne(s) publique(s) dans {irve.rayonKm} km
              {irve.plusProcheKm != null ? ` · la plus proche à ${irve.plusProcheKm} km` : ""} — non équipé sur site.
            </span>
          ) : (
            <span className="text-[var(--muted)]">
              Aucune borne publique connue dans {irve.rayonKm} km (données IRVE).
            </span>
          )}
        </div>
      )}

      {adresseComplete && (
        <div className="mb-3 flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm">
          <span className="flex-1 text-slate-700">📍 {adresseComplete}</span>
          <button
            onClick={copier}
            className="shrink-0 rounded-md border border-[var(--border)] px-2 py-1 text-xs font-medium hover:bg-white"
          >
            {copie ? "Copié ✓" : "Copier"}
          </button>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <a
          href="https://maps.rossinienergy.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg bg-[var(--brand)] px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
        >
          ⚡ Carte Rossini Energy
        </a>
        <a
          href="https://chargemap.com/fr-fr/map"
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm font-medium hover:bg-slate-50"
        >
          🔌 Chargemap
        </a>
      </div>
    </div>
  );
}
