"use client";

import "leaflet/dist/leaflet.css";
import { useEffect, useState } from "react";
import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import type { FeatureCollection } from "geojson";

export type BornesMapProps = { counts: Record<string, number> };

// Échelle choroplèthe (nb de bornes par département). Seuils volontairement
// lisibles ; couleurs froid→dense.
export function densiteColor(n: number): string {
  if (n > 3000) return "#08519c";
  if (n > 1500) return "#3182bd";
  if (n > 700) return "#6baed6";
  if (n > 300) return "#9ecae1";
  if (n > 100) return "#c6dbef";
  if (n > 0) return "#eff3ff";
  return "#f1f5f9";
}

export const DENSITE_PALIERS = [
  { label: "> 3000", min: 3001 },
  { label: "1501–3000", min: 1501 },
  { label: "701–1500", min: 701 },
  { label: "301–700", min: 301 },
  { label: "101–300", min: 101 },
  { label: "1–100", min: 1 },
];

export default function BornesMap({ counts }: BornesMapProps) {
  const [geo, setGeo] = useState<FeatureCollection | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(
      "https://geo.api.gouv.fr/departements?fields=nom,code&format=geojson&geometry=contour",
    )
      .then((r) => r.json())
      .then((gj) => {
        if (!cancelled) setGeo(gj as FeatureCollection);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <MapContainer
      center={[46.6, 2.4]}
      zoom={5}
      scrollWheelZoom={false}
      className="h-[460px] w-full"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {geo && (
        <GeoJSON
          key={Object.keys(counts).length}
          data={geo}
          style={(feature) => {
            const code = (feature?.properties?.code as string) ?? "";
            return {
              fillColor: densiteColor(counts[code] ?? 0),
              fillOpacity: 0.75,
              color: "#ffffff",
              weight: 1,
            };
          }}
          onEachFeature={(feature, layer) => {
            const code = (feature.properties?.code as string) ?? "";
            const nom = (feature.properties?.nom as string) ?? code;
            const n = counts[code] ?? 0;
            layer.bindTooltip(`${nom} (${code}) — ${n.toLocaleString("fr-FR")} bornes`, {
              sticky: true,
            });
          }}
        />
      )}
    </MapContainer>
  );
}
