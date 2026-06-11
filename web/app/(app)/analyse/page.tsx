import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { AnalyseWorkbench } from "@/components/analyse-workbench";

export const dynamic = "force-dynamic";

// Landing dédiée aux analyses d'images satellite / captures GMaps par Magellan.
// Liste à gauche (historique), espace de travail à droite (upload OU affichage
// de l'analyse courante via ?id=...).
export default async function AnalysePage({
  searchParams,
}: {
  searchParams: Promise<{ id?: string }>;
}) {
  const { id } = await searchParams;
  const supabase = await createClient();

  const { data: rows } = await supabase
    .from("image_analyses")
    .select("id, source, label, address, created_at")
    .order("created_at", { ascending: false })
    .limit(40);
  type Row = {
    id: string;
    source: "upload" | "capture";
    label: string | null;
    address: string | null;
    created_at: string;
  };
  const liste = (rows as Row[] | null) ?? [];

  // Si une analyse est demandée, on récupère son détail + une URL signée pour
  // afficher l'image (le bucket est privé).
  let current: {
    id: string;
    source: "upload" | "capture";
    label: string | null;
    address: string | null;
    lat: number | null;
    lng: number | null;
    zoom: number | null;
    image_url: string | null;
    result: Record<string, unknown>;
    leads: Record<string, string>;
    created_at: string;
  } | null = null;

  if (id) {
    const { data } = await supabase
      .from("image_analyses")
      .select("id, source, label, address, lat, lng, zoom, image_path, result, leads, created_at")
      .eq("id", id)
      .maybeSingle();
    if (data) {
      const d = data as {
        id: string;
        source: "upload" | "capture";
        label: string | null;
        address: string | null;
        lat: number | null;
        lng: number | null;
        zoom: number | null;
        image_path: string;
        result: Record<string, unknown>;
        leads: Record<string, string> | null;
        created_at: string;
      };
      const signed = await supabase.storage
        .from("analyses")
        .createSignedUrl(d.image_path, 60 * 60);
      current = {
        id: d.id,
        source: d.source,
        label: d.label,
        address: d.address,
        lat: d.lat,
        lng: d.lng,
        zoom: d.zoom,
        image_url: signed.data?.signedUrl ?? null,
        result: d.result ?? {},
        leads: d.leads ?? {},
        created_at: d.created_at,
      };
    }
  }

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">🧭 Analyse guidée par M</h1>
          <p className="text-sm text-[var(--muted)]">
            Donne-moi une capture satellite ou une photo aérienne — j&apos;identifie
            les entreprises, le terrain et les opportunités pour toi.
          </p>
        </div>
        <Link
          href="/recherche"
          className="rounded-lg border border-[var(--border)] bg-white px-3 py-1.5 text-sm font-medium text-[var(--muted)] hover:bg-slate-50"
        >
          ← Explorer une zone (GMaps)
        </Link>
      </div>

      <div className="grid gap-4 lg:grid-cols-[18rem_1fr]">
        {/* Colonne gauche : historique */}
        <aside className="space-y-2">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            Mes analyses ({liste.length})
          </h2>
          {liste.length === 0 ? (
            <p className="rounded-xl border border-dashed border-[var(--border)] bg-white p-4 text-xs text-[var(--muted)]">
              Aucune analyse pour l&apos;instant. Lance la première à droite.
            </p>
          ) : (
            <ul className="max-h-[36rem] space-y-1 overflow-y-auto">
              {liste.map((r) => {
                const active = current?.id === r.id;
                const date = new Date(r.created_at).toLocaleString("fr-FR", {
                  day: "2-digit",
                  month: "short",
                  hour: "2-digit",
                  minute: "2-digit",
                });
                const titre = r.label || r.address || (r.source === "capture" ? "Capture GMaps" : "Image importée");
                return (
                  <li key={r.id}>
                    <Link
                      href={`/analyse?id=${r.id}`}
                      className={`block rounded-lg border px-3 py-2 text-sm transition ${
                        active
                          ? "border-[var(--brand)] bg-[var(--brand)]/5 text-[var(--brand)]"
                          : "border-[var(--border)] bg-white text-slate-700 hover:bg-slate-50"
                      }`}
                    >
                      <div className="truncate font-medium">
                        {r.source === "capture" ? "📷" : "📁"} {titre}
                      </div>
                      <div className="text-xs text-[var(--muted)]">{date}</div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </aside>

        {/* Colonne droite : workbench (client) */}
        <section>
          <AnalyseWorkbench current={current} />
        </section>
      </div>
    </div>
  );
}
