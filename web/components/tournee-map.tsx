"use client";

import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useEffect } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Polyline,
  Popup,
  Tooltip,
  useMap,
} from "react-leaflet";
import { CATEGORIE_META } from "@/lib/tournees";
import type { Itineraire } from "@/lib/itineraire";

export type TourneeMapProps = { itineraire: Itineraire };

// Pastille numérotée colorée par catégorie (l'ordre de visite saute aux yeux).
function pastille(numero: number, color: string): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div style="background:${color};color:#fff;width:24px;height:24px;border-radius:9999px;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;">${numero}</div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
}

// Pin de départ « ma position » (losange neutre, distinct des visites).
const DEPART_ICON = L.divIcon({
  className: "",
  html: `<div style="background:#1e293b;color:#fff;width:22px;height:22px;border-radius:6px;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;font-size:11px;">🚩</div>`,
  iconSize: [22, 22],
  iconAnchor: [11, 11],
});

function FitBounds({ pts }: { pts: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (pts.length === 0) return;
    map.fitBounds(pts, { padding: [48, 48], maxZoom: 12 });
  }, [map, pts]);
  return null;
}

export default function TourneeMap({ itineraire }: TourneeMapProps) {
  const { depart, etapes } = itineraire;
  // Le départ « ma position » est un point distinct ; sinon il coïncide avec la 1ʳᵉ visite.
  const departExterne = depart.label === "Ma position";

  const ligne: [number, number][] = [
    ...(departExterne ? [[depart.lat, depart.lng] as [number, number]] : []),
    ...etapes.map((e) => [e.point.lat, e.point.lng] as [number, number]),
  ];

  return (
    <MapContainer center={[46.6, 2.4]} zoom={6} scrollWheelZoom className="h-[520px] w-full">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitBounds pts={ligne} />

      {ligne.length > 1 && (
        <Polyline
          positions={ligne}
          pathOptions={{ color: "#1f7a4d", weight: 3, opacity: 0.6, dashArray: "6 8" }}
        />
      )}

      {departExterne && (
        <Marker position={[depart.lat, depart.lng]} icon={DEPART_ICON}>
          <Tooltip direction="top">Départ — {depart.label}</Tooltip>
        </Marker>
      )}

      {etapes.map((e) => {
        const meta = CATEGORIE_META[e.point.categorie];
        return (
          <Marker
            key={e.point.lead.id}
            position={[e.point.lat, e.point.lng]}
            icon={pastille(e.ordre, meta.color)}
          >
            <Popup>
              <div className="space-y-1">
                <div className="font-semibold">
                  {e.ordre}. {e.point.lead.entreprise}
                </div>
                <div className="text-xs">
                  {meta.emoji} {meta.label}
                  {e.point.lead.ville ? ` · ${e.point.lead.ville}` : ""}
                  {e.point.lead.score != null ? ` · ${e.point.lead.score}/100` : ""}
                </div>
                <div className="text-xs text-slate-500">
                  {e.legKm > 0 ? `+${e.legKm} km` : "point de départ"} · cumul {e.cumulKm} km
                </div>
                {e.point.lead.contact_tel && (
                  <a
                    href={`tel:${e.point.lead.contact_tel.replace(/\s/g, "")}`}
                    className="text-xs underline"
                  >
                    📞 {e.point.lead.contact_tel}
                  </a>
                )}
                <div>
                  <a href={`/leads/${e.point.lead.id}`} className="text-xs font-medium underline">
                    Ouvrir la fiche →
                  </a>
                </div>
              </div>
            </Popup>
          </Marker>
        );
      })}
    </MapContainer>
  );
}
