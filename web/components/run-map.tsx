"use client";

import "leaflet/dist/leaflet.css";
import { useEffect } from "react";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Popup,
  useMap,
} from "react-leaflet";

export type MapLead = {
  id: string;
  entreprise: string;
  ville?: string | null;
  score: number | null;
  latitude: number | null;
  longitude: number | null;
};

export type RunMapProps = {
  departement?: string | null;
  adresse?: string | null;
  rayonKm?: number | null;
  leads: MapLead[];
};

/** Couleur d'un drapeau : froid (bleu) → chaud (rouge) selon la qualification. */
export function scoreToColor(score: number | null): string {
  if (score == null) return "#94a3b8"; // gris — non scoré
  if (score >= 85) return "#dc2626"; // rouge — très chaud
  if (score >= 70) return "#f97316"; // orange
  if (score >= 55) return "#f59e0b"; // ambre
  if (score >= 40) return "#22d3ee"; // cyan
  return "#3b82f6"; // bleu — froid
}

const geoloc = (l: MapLead): l is MapLead & { latitude: number; longitude: number } =>
  typeof l.latitude === "number" && typeof l.longitude === "number";

/**
 * Trace la zone de recherche (contour du département en bleu, ou cercle autour
 * d'une adresse) et cadre la carte dessus. À défaut, cadre sur les drapeaux.
 */
function ZoneOverlay({ departement, adresse, rayonKm, leads }: RunMapProps) {
  const map = useMap();
  useEffect(() => {
    let cancelled = false;
    let layer: import("leaflet").Layer | null = null;

    async function setup() {
      const L = (await import("leaflet")).default;
      const fitMarkers = () => {
        const pts = leads
          .filter(geoloc)
          .map((l) => [l.latitude, l.longitude] as [number, number]);
        if (pts.length && !cancelled) {
          map.fitBounds(L.latLngBounds(pts), { padding: [30, 30], maxZoom: 13 });
        }
      };

      if (departement) {
        try {
          const res = await fetch(
            `https://geo.api.gouv.fr/departements/${departement}?fields=contour&format=geojson`,
          );
          if (res.ok && !cancelled) {
            const gj = await res.json();
            layer = L.geoJSON(gj, {
              style: {
                color: "#2563eb",
                weight: 2,
                fillColor: "#2563eb",
                fillOpacity: 0.06,
              },
            }).addTo(map);
            map.fitBounds((layer as import("leaflet").GeoJSON).getBounds(), {
              padding: [20, 20],
            });
            return;
          }
        } catch {
          /* on retombe sur le cadrage par drapeaux */
        }
      } else if (adresse) {
        try {
          const res = await fetch(
            `https://api-adresse.data.gouv.fr/search/?q=${encodeURIComponent(adresse)}&limit=1`,
          );
          const data = await res.json();
          const f = data?.features?.[0];
          if (f && !cancelled) {
            const [lon, lat] = f.geometry.coordinates as [number, number];
            const circle = L.circle([lat, lon], {
              radius: (rayonKm ?? 10) * 1000,
              color: "#2563eb",
              weight: 2,
              fillColor: "#2563eb",
              fillOpacity: 0.06,
            }).addTo(map);
            layer = circle;
            map.fitBounds(circle.getBounds(), { padding: [20, 20] });
            return;
          }
        } catch {
          /* idem */
        }
      }
      fitMarkers();
    }

    setup();
    return () => {
      cancelled = true;
      if (layer) map.removeLayer(layer);
    };
    // leads volontairement hors deps : tableau stable au montage de la carte.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, departement, adresse, rayonKm]);

  return null;
}

export default function RunMap({
  departement,
  adresse,
  rayonKm,
  leads,
}: RunMapProps) {
  const points = leads.filter(geoloc);
  return (
    <MapContainer
      center={[46.6, 2.4]}
      zoom={6}
      scrollWheelZoom
      className="h-[420px] w-full"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <ZoneOverlay
        departement={departement}
        adresse={adresse}
        rayonKm={rayonKm}
        leads={leads}
      />
      {points.map((l) => (
        <CircleMarker
          key={l.id}
          center={[l.latitude, l.longitude]}
          radius={7}
          pathOptions={{
            color: "#ffffff",
            weight: 1.5,
            fillColor: scoreToColor(l.score),
            fillOpacity: 0.95,
          }}
        >
          <Popup>
            <span className="font-medium">{l.entreprise}</span>
            {l.ville ? ` · ${l.ville}` : ""} — score {l.score ?? "—"}
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
