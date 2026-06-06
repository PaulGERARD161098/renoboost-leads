"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  APIProvider,
  Map,
  useMap,
  useMapsLibrary,
} from "@vis.gl/react-google-maps";

// PD — Explorateur GMaps satellite : 2ᵉ grand badge dans /recherche.
// Carte satellite déplaçable, recherche d'adresses (Places Autocomplete),
// mémoire du dernier point centré (localStorage), et bouton « Capturer &
// analyser » qui envoie la vue à Magellan (Claude Vision) puis ouvre la
// landing /analyse?id=...

const LS_KEY = "leads:last_map_view";
const MAP_ID = "leads-explorer-map";

type View = { lat: number; lng: number; zoom: number; address?: string | null };

function readLastView(): View {
  const fallback: View = { lat: 48.8566, lng: 2.3522, zoom: 13, address: null }; // Paris
  if (typeof window === "undefined") return fallback;
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return fallback;
    const p = JSON.parse(raw);
    if (
      typeof p?.lat === "number" &&
      typeof p?.lng === "number" &&
      typeof p?.zoom === "number"
    ) {
      return { lat: p.lat, lng: p.lng, zoom: p.zoom, address: p.address ?? null };
    }
  } catch {
    /* no-op */
  }
  return fallback;
}

function writeLastView(v: View): void {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(v));
  } catch {
    /* no-op */
  }
}

// Champ de recherche d'adresses (Places Autocomplete custom). Au clic d'une
// suggestion, re-centre la carte via le callback parent.
function PlacesSearch({
  initial,
  onPick,
}: {
  initial: string;
  onPick: (lat: number, lng: number, address: string) => void;
}) {
  const placesLib = useMapsLibrary("places");
  const [q, setQ] = useState(initial);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [predictions, setPredictions] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const acRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const psRef = useRef<any>(null);

  useEffect(() => {
    if (!placesLib) return;
    acRef.current = new placesLib.AutocompleteService();
    psRef.current = new placesLib.PlacesService(document.createElement("div"));
  }, [placesLib]);

  useEffect(() => {
    if (!acRef.current || q.trim().length < 3) {
      setPredictions([]);
      return;
    }
    const id = setTimeout(() => {
      acRef.current.getPlacePredictions(
        { input: q, language: "fr", componentRestrictions: { country: ["fr"] } },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (preds: any[] | null) => setPredictions(preds ?? []),
      );
    }, 200);
    return () => clearTimeout(id);
  }, [q]);

  function pick(placeId: string, description: string) {
    if (!psRef.current) return;
    psRef.current.getDetails(
      { placeId, fields: ["geometry", "formatted_address"] },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (place: any, status: any) => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const okStatus = (window as any).google?.maps?.places?.PlacesServiceStatus?.OK;
        if (status !== okStatus || !place?.geometry?.location) return;
        const lat = place.geometry.location.lat();
        const lng = place.geometry.location.lng();
        const addr = place.formatted_address ?? description;
        onPick(lat, lng, addr);
        setQ(addr);
        setPredictions([]);
        setOpen(false);
      },
    );
  }

  return (
    <div className="relative">
      <input
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
        placeholder="Chercher une adresse, une entreprise…"
        className="w-full rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
      />
      {open && predictions.length > 0 && (
        <ul className="absolute left-0 right-0 top-full z-10 mt-1 max-h-64 overflow-y-auto rounded-lg border border-[var(--border)] bg-white shadow-lg">
          {predictions.map((p) => (
            <li key={p.place_id}>
              <button
                type="button"
                onMouseDown={() => pick(p.place_id, p.description)}
                className="block w-full px-3 py-2 text-left text-sm hover:bg-slate-50"
              >
                {p.description}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ExplorerMapInner() {
  const router = useRouter();
  const [view, setView] = useState<View>(() => readLastView());
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const map = useMap(MAP_ID);

  function onIdle() {
    if (!map) return;
    const c = map.getCenter();
    const z = map.getZoom();
    if (!c || z == null) return;
    const next: View = {
      lat: c.lat(),
      lng: c.lng(),
      zoom: z,
      address: view.address ?? null,
    };
    setView(next);
    writeLastView(next);
  }

  function recentrer(lat: number, lng: number, address: string) {
    if (map) {
      map.panTo({ lat, lng });
      map.setZoom(18);
    }
    const next: View = { lat, lng, zoom: 18, address };
    setView(next);
    writeLastView(next);
  }

  async function captureAndAnalyse() {
    setError(null);
    setAnalyzing(true);
    try {
      const cap = await fetch(
        `/api/analyse/capture?lat=${view.lat}&lng=${view.lng}&zoom=${view.zoom}`,
      );
      if (!cap.ok) {
        const j = await cap.json().catch(() => ({}));
        throw new Error(j.error ?? "Capture impossible.");
      }
      const blob = await cap.blob();
      const fd = new FormData();
      fd.set("image", new File([blob], "capture.png", { type: blob.type || "image/png" }));
      fd.set("source", "capture");
      fd.set("lat", String(view.lat));
      fd.set("lng", String(view.lng));
      fd.set("zoom", String(view.zoom));
      if (view.address) fd.set("address", view.address);
      const run = await fetch("/api/analyse/run", { method: "POST", body: fd });
      const data = await run.json();
      if (!run.ok) throw new Error(data.error ?? "Analyse impossible.");
      router.push(`/analyse?id=${data.id}`);
    } catch (e) {
      setError((e as Error).message);
      setAnalyzing(false);
    }
  }

  return (
    <div className="space-y-3">
      <PlacesSearch initial={view.address ?? ""} onPick={recentrer} />

      <div className="overflow-hidden rounded-xl border border-[var(--border)]">
        <Map
          id={MAP_ID}
          defaultCenter={{ lat: view.lat, lng: view.lng }}
          defaultZoom={view.zoom}
          mapTypeId="satellite"
          gestureHandling="greedy"
          disableDefaultUI={false}
          style={{ width: "100%", height: "420px" }}
          onIdle={onIdle}
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={captureAndAnalyse}
          disabled={analyzing}
          className="inline-flex items-center gap-2 rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white transition hover:bg-[var(--brand-dark)] disabled:opacity-50"
        >
          {analyzing ? "Analyse en cours…" : "📷 Capturer & analyser cette vue"}
        </button>
        <p className="text-xs text-[var(--muted)]">
          Magellan extrait les entreprises, le terrain (toiture / parking / ombrières / bornes VE) et te propose un angle commercial.
        </p>
      </div>

      {error && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}

export function ExplorerMap() {
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
  if (!apiKey) {
    return (
      <div className="rounded-xl border border-dashed border-[var(--border)] bg-white p-6 text-sm text-[var(--muted)]">
        Carte Google Maps indisponible : ajoute la variable{" "}
        <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">
          NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
        </code>{" "}
        dans Vercel pour activer l&apos;explorateur satellite.
      </div>
    );
  }
  return (
    <APIProvider apiKey={apiKey} libraries={["places"]}>
      <ExplorerMapInner />
    </APIProvider>
  );
}
