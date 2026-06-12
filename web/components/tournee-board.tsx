"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { CATEGORIE_META, type CategorieTournee, type PointTournee } from "@/lib/tournees";
import { planifierItineraire, lienGoogleMaps } from "@/lib/itineraire";

// Leaflet a besoin du DOM : chargement client uniquement.
const TourneeMap = dynamic(() => import("./tournee-map"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[520px] w-full items-center justify-center bg-slate-50 text-sm text-[var(--muted)]">
      Chargement de la carte…
    </div>
  ),
});

type Origin = { lat: number; lng: number; label: string } | null;

// Carte des tournées + planificateur d'itinéraire (charte agent-first : on
// PROPOSE l'ordre des visites, pas seulement leurs positions). L'utilisateur
// choisit son départ (1ʳᵉ visite par défaut, ou « ma position »).
export function TourneeBoard({ points }: { points: PointTournee[] }) {
  const [origin, setOrigin] = useState<Origin>(null);
  const [geoState, setGeoState] = useState<"idle" | "pending" | "error">("idle");

  const itineraire = useMemo(
    () => planifierItineraire(points, origin),
    [points, origin],
  );
  const lien = lienGoogleMaps(itineraire);

  function partirDeMaPosition() {
    if (!navigator.geolocation) {
      setGeoState("error");
      return;
    }
    setGeoState("pending");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setOrigin({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          label: "Ma position",
        });
        setGeoState("idle");
      },
      () => setGeoState("error"),
      { enableHighAccuracy: true, timeout: 8000 },
    );
  }

  const cats: CategorieTournee[] = ["rdv", "chaud", "tiede"];

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
      <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-white">
        <TourneeMap itineraire={itineraire} />
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-[var(--border)] px-4 py-2 text-xs text-[var(--muted)]">
          {cats.map((c) => (
            <span key={c} className="inline-flex items-center gap-1">
              <span
                className="inline-block h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: CATEGORIE_META[c].color }}
              />
              {CATEGORIE_META[c].emoji} {CATEGORIE_META[c].label}
            </span>
          ))}
          <span className="inline-flex items-center gap-1">
            <span className="text-[10px]">🚩</span> Départ
          </span>
        </div>
      </div>

      {/* ── Itinéraire proposé ── */}
      <div className="rounded-xl border border-[var(--border)] bg-white p-4">
        <div className="mb-1 flex items-baseline justify-between gap-2">
          <h2 className="text-sm font-bold">🧭 Itinéraire du jour</h2>
          <span className="text-xs font-semibold text-[var(--brand)]">
            {itineraire.distanceTotaleKm} km · ~{dureeTexte(itineraire.dureeRouteMin)}
          </span>
        </div>
        <p className="mb-3 text-xs text-[var(--muted)]">
          Ordre optimisé des {itineraire.etapes.length} visite
          {itineraire.etapes.length > 1 ? "s" : ""}, départ depuis{" "}
          <span className="font-medium">{itineraire.depart.label}</span>.
        </p>

        <div className="mb-3 flex flex-wrap gap-2">
          <button
            onClick={partirDeMaPosition}
            disabled={geoState === "pending"}
            className="rounded-lg border border-[var(--border)] px-2.5 py-1 text-xs font-medium hover:bg-slate-50 disabled:opacity-40"
          >
            {geoState === "pending" ? "Localisation…" : "📍 Partir de ma position"}
          </button>
          {origin && (
            <button
              onClick={() => setOrigin(null)}
              className="rounded-lg border border-[var(--border)] px-2.5 py-1 text-xs font-medium hover:bg-slate-50"
            >
              ↺ Départ = 1ʳᵉ visite
            </button>
          )}
        </div>
        {geoState === "error" && (
          <p className="mb-3 text-xs text-amber-700">
            Localisation indisponible — itinéraire au départ de la 1ʳᵉ visite.
          </p>
        )}

        <ol className="space-y-1.5">
          {itineraire.etapes.map((e) => {
            const meta = CATEGORIE_META[e.point.categorie];
            return (
              <li key={e.point.lead.id} className="flex items-start gap-2 text-sm">
                <span
                  className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white"
                  style={{ backgroundColor: meta.color }}
                >
                  {e.ordre}
                </span>
                <span className="min-w-0">
                  <a href={`/leads/${e.point.lead.id}`} className="font-medium hover:underline">
                    {e.point.lead.entreprise}
                  </a>
                  <span className="block text-xs text-[var(--muted)]">
                    {meta.emoji} {e.point.lead.ville ?? "—"}
                    {e.legKm > 0 ? ` · +${e.legKm} km` : " · départ"}
                  </span>
                </span>
              </li>
            );
          })}
        </ol>

        {lien && (
          <a
            href={lien}
            target="_blank"
            rel="noreferrer"
            className="mt-3 flex w-full items-center justify-center rounded-lg bg-[var(--brand)] px-3 py-2 text-sm font-semibold text-white hover:bg-[var(--brand-dark)]"
          >
            🗺️ Ouvrir dans Google Maps
          </a>
        )}
        {itineraire.etapes.length > 10 && (
          <p className="mt-2 text-[11px] text-[var(--muted)]">
            Google Maps limite à 10 arrêts — le lien couvre les 10 premières visites
            de l&apos;ordre proposé.
          </p>
        )}
      </div>
    </div>
  );
}

function dureeTexte(min: number): string {
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m ? `${h} h ${m.toString().padStart(2, "0")}` : `${h} h`;
}
