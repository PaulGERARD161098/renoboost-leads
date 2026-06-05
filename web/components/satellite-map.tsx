"use client";

import { CircleMarker, MapContainer, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";

// Carte orthophoto IGN déplaçable, centrée sur l'adresse du prospect.
// Tuiles WMTS Géoplateforme (gratuites). Pas de marqueur image (icône Leaflet
// par défaut KO en bundling) → un cercle vectoriel marque le centre.
const TUILES_IGN =
  "https://data.geopf.fr/wmts?LAYER=ORTHOIMAGERY.ORTHOPHOTOS" +
  "&EXCEPTIONS=text/xml&FORMAT=image/jpeg&SERVICE=WMTS&VERSION=1.0.0" +
  "&REQUEST=GetTile&STYLE=normal&TILEMATRIXSET=PM" +
  "&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}";

export default function SatelliteMap({ lat, lon }: { lat: number; lon: number }) {
  return (
    <MapContainer
      center={[lat, lon]}
      zoom={18}
      maxZoom={19}
      scrollWheelZoom
      style={{ height: "100%", width: "100%", borderRadius: "0.5rem" }}
    >
      <TileLayer
        url={TUILES_IGN}
        attribution="© IGN / Géoplateforme"
        maxZoom={19}
        tileSize={256}
      />
      <CircleMarker
        center={[lat, lon]}
        radius={9}
        pathOptions={{ color: "#10b981", weight: 3, fillColor: "#10b981", fillOpacity: 0.25 }}
      />
    </MapContainer>
  );
}
