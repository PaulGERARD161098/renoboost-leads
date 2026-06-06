import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { runVisionAnalyse, type AnalyseContext } from "@/lib/analyse";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MAX_BYTES = 8 * 1024 * 1024; // 8 Mo, garde-fou budget Vision

function parseNum(v: FormDataEntryValue | null): number | null {
  if (typeof v !== "string" || v.trim() === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export async function POST(req: NextRequest) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Non authentifié." }, { status: 401 });
  }

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { error: "Magellan Vision indisponible (ANTHROPIC_API_KEY absente)." },
      { status: 503 },
    );
  }

  const form = await req.formData();
  const file = form.get("image");
  if (!(file instanceof File)) {
    return NextResponse.json({ error: "Image manquante." }, { status: 400 });
  }
  if (file.size > MAX_BYTES) {
    return NextResponse.json(
      { error: "Image trop lourde (max 8 Mo)." },
      { status: 413 },
    );
  }
  const mt = file.type;
  const mediaType: "image/png" | "image/jpeg" | "image/webp" =
    mt === "image/jpeg" || mt === "image/jpg"
      ? "image/jpeg"
      : mt === "image/webp"
        ? "image/webp"
        : "image/png";

  const source = (form.get("source") === "capture" ? "capture" : "upload") as
    | "capture"
    | "upload";
  const label = (form.get("label")?.toString().trim() || null) as string | null;
  const address = (form.get("address")?.toString().trim() || null) as string | null;
  const lat = parseNum(form.get("lat"));
  const lng = parseNum(form.get("lng"));
  const zoom = parseNum(form.get("zoom"));

  // 1) Upload de l'image dans le bucket Storage (sous le dossier de l'user
  // pour que la policy RLS Storage ne le rejette pas).
  const ext = mediaType === "image/jpeg" ? "jpg" : mediaType === "image/webp" ? "webp" : "png";
  const path = `${user.id}/${crypto.randomUUID()}.${ext}`;
  const buffer = Buffer.from(await file.arrayBuffer());
  const up = await supabase.storage.from("analyses").upload(path, buffer, {
    contentType: mediaType,
    upsert: false,
  });
  if (up.error) {
    return NextResponse.json(
      { error: `Upload image: ${up.error.message}` },
      { status: 500 },
    );
  }

  // 2) Analyse Vision.
  const ctx: AnalyseContext = { address, lat, lng, zoom: zoom != null ? Math.round(zoom) : null, source };
  const draft = await runVisionAnalyse(apiKey, buffer.toString("base64"), mediaType, ctx);
  if (!draft.ok) {
    // Nettoyage best-effort de l'image stockée.
    await supabase.storage.from("analyses").remove([path]).catch(() => {});
    return NextResponse.json({ error: draft.error }, { status: draft.status });
  }

  // 3) Persistence du résultat.
  const { data: inserted, error: insErr } = await supabase
    .from("image_analyses")
    .insert({
      user_id: user.id,
      source,
      label,
      address,
      lat,
      lng,
      zoom: zoom != null ? Math.round(zoom) : null,
      image_path: path,
      result: draft.result,
    })
    .select("id, created_at")
    .single();
  if (insErr) {
    await supabase.storage.from("analyses").remove([path]).catch(() => {});
    return NextResponse.json({ error: insErr.message }, { status: 500 });
  }

  return NextResponse.json({
    id: (inserted as { id: string }).id,
    result: draft.result,
  });
}
