import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Génère une capture satellite Google Maps via l'API Static Maps : on demande
// la vue serveur-side pour avoir un PNG fiable (contourne les limites
// CORS/tiles de la carte cliente). Renvoie le PNG brut.
export async function GET(req: NextRequest) {
  const apiKey = process.env.GOOGLE_MAPS_SERVER_KEY || process.env.GOOGLE_MAPS_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { error: "Capture indisponible (GOOGLE_MAPS_SERVER_KEY absente)." },
      { status: 503 },
    );
  }
  const url = new URL(req.url);
  const lat = parseFloat(url.searchParams.get("lat") ?? "");
  const lng = parseFloat(url.searchParams.get("lng") ?? "");
  const zoom = parseInt(url.searchParams.get("zoom") ?? "18", 10);
  if (Number.isNaN(lat) || Number.isNaN(lng)) {
    return NextResponse.json({ error: "lat/lng requis." }, { status: 400 });
  }

  const params = new URLSearchParams({
    center: `${lat},${lng}`,
    zoom: String(Math.max(1, Math.min(21, zoom))),
    size: "640x640",
    scale: "2",
    maptype: "satellite",
    key: apiKey,
  });
  const target = `https://maps.googleapis.com/maps/api/staticmap?${params.toString()}`;
  const res = await fetch(target);
  if (!res.ok) {
    return NextResponse.json(
      { error: `Static Maps a renvoyé ${res.status}.` },
      { status: 502 },
    );
  }
  const buf = await res.arrayBuffer();
  return new NextResponse(buf, {
    headers: {
      "content-type": res.headers.get("content-type") ?? "image/png",
      "cache-control": "private, max-age=60",
    },
  });
}
