"use client";

import "leaflet/dist/leaflet.css";
import { useEffect } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";
import { CATEGORIE_META, type PointTournee } from "@/lib/tournees";

export type TourneeMapProps = { points: PointTournee[] };

// Recadre la carte sur l'ensemble des points à chaque changement de jeu.
function FitBounds({ points }: TourneeMapProps) {
  const map = useMap();
  useEffect(() => {
    if (points.length === 0) return;
    const bounds: [number, number][] = points.map((p) => [p.lat, p.lng]);
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 12 });
  }, [map, points]);
  return null;
}

export default function TourneeMap({ points }: TourneeMapProps) {
  return (
    <MapContainer center={[46.6, 2.4]} zoom={6} scrollWheelZoom className="h-[520px] w-full">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitBounds points={points} />
      {points.map((p) => {
        const meta = CATEGORIE_META[p.categorie];
        return (
          <CircleMarker
            key={p.lead.id}
            center={[p.lat, p.lng]}
            radius={p.categorie === "rdv" ? 10 : 7}
            pathOptions={{
              color: "#ffffff",
              weight: 1.5,
              fillColor: meta.color,
              fillOpacity: 0.9,
            }}
          >
            <Popup>
              <div className="space-y-1">
                <div className="font-semibold">{p.lead.entreprise}</div>
                <div className="text-xs">
                  {meta.emoji} {meta.label}
                  {p.lead.ville ? ` · ${p.lead.ville}` : ""}
                  {p.lead.score != null ? ` · ${p.lead.score}/100` : ""}
                </div>
                {p.lead.contact_tel && (
                  <a href={`tel:${p.lead.contact_tel.replace(/\s/g, "")}`} className="text-xs underline">
                    📞 {p.lead.contact_tel}
                  </a>
                )}
                <div>
                  <a href={`/leads/${p.lead.id}`} className="text-xs font-medium underline">
                    Ouvrir la fiche →
                  </a>
                </div>
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
