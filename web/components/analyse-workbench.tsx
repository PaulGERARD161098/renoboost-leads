"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { AnalyseResult } from "@/lib/analyse";

// Workbench de la page /analyse :
//  • Si aucune analyse n'est ouverte → zone d'upload (drag & drop ou bouton).
//  • Si une analyse est ouverte → image + résultat structuré (entreprises,
//    terrain, opportunités, accroche prête à copier).
export function AnalyseWorkbench({
  current,
}: {
  current: {
    id: string;
    source: "upload" | "capture";
    label: string | null;
    address: string | null;
    lat: number | null;
    lng: number | null;
    zoom: number | null;
    image_url: string | null;
    result: Record<string, unknown>;
    created_at: string;
  } | null;
}) {
  if (current) return <AnalyseDetail current={current} />;
  return <Uploader />;
}

function Uploader() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [label, setLabel] = useState("");
  const [address, setAddress] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [over, setOver] = useState(false);

  function pickFile(f: File | null) {
    if (!f) return;
    if (!/^image\//.test(f.type)) {
      setError("Format non supporté (JPG, PNG, WebP).");
      return;
    }
    setError(null);
    setFile(f);
  }

  async function lancer() {
    if (!file) return;
    setError(null);
    setBusy(true);
    try {
      const fd = new FormData();
      fd.set("image", file);
      fd.set("source", "upload");
      if (label.trim()) fd.set("label", label.trim());
      if (address.trim()) fd.set("address", address.trim());
      const res = await fetch("/api/analyse/run", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Analyse impossible.");
      router.push(`/analyse?id=${data.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4 rounded-2xl border border-[var(--border)] bg-white p-5">
      <div>
        <h2 className="text-base font-bold">Importe une capture / une photo aérienne</h2>
        <p className="text-sm text-[var(--muted)]">
          Astuce : depuis l&apos;onglet Recherches, tu peux aussi capturer la vue
          GMaps en 1 clic — la carte garde toujours ton dernier point.
        </p>
      </div>

      {/* Dropzone */}
      <label
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          pickFile(e.dataTransfer.files?.[0] ?? null);
        }}
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition ${
          over
            ? "border-[var(--brand)] bg-[var(--brand)]/5"
            : "border-[var(--border)] bg-slate-50 hover:bg-slate-100"
        }`}
      >
        <span className="text-3xl">{file ? "🖼️" : "📥"}</span>
        <span className="text-sm font-medium">
          {file ? file.name : "Glisse une image ici"}
        </span>
        <span className="text-xs text-[var(--muted)]">
          {file
            ? `${(file.size / 1024).toFixed(0)} Ko · ${file.type}`
            : "ou clique pour parcourir (JPG, PNG, WebP — 8 Mo max)"}
        </span>
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="hidden"
          onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
        />
      </label>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--muted)]">
            Libellé (optionnel)
          </label>
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Ex. Zone d'activité Lille Lesquin"
            className="w-full rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm outline-none focus:border-[var(--brand)]"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--muted)]">
            Adresse / lieu (optionnel)
          </label>
          <input
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="Ex. 12 rue de l'industrie, 59000 Lille"
            className="w-full rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm outline-none focus:border-[var(--brand)]"
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={lancer}
          disabled={!file || busy}
          className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white transition hover:bg-[var(--brand-dark)] disabled:opacity-40"
        >
          {busy ? "Analyse en cours…" : "🧭 Lancer l'analyse Magellan"}
        </button>
        {busy && (
          <span className="text-xs text-[var(--muted)]">
            Magellan lit l&apos;image et structure les opportunités…
          </span>
        )}
      </div>

      {error && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      )}
    </div>
  );
}

// Cast permissif : `result` arrive de la base en jsonb non typé. On le traite
// défensivement à l'affichage (champs optionnels, listes par défaut).
function asResult(r: Record<string, unknown>): Partial<AnalyseResult> {
  return (r ?? {}) as Partial<AnalyseResult>;
}

function AnalyseDetail({
  current,
}: {
  current: NonNullable<Parameters<typeof AnalyseWorkbench>[0]["current"]>;
}) {
  const router = useRouter();
  const r = asResult(current.result);
  const date = new Date(current.created_at).toLocaleString("fr-FR");
  const titre =
    current.label || current.address || (current.source === "capture" ? "Capture GMaps" : "Image importée");
  const [copied, setCopied] = useState<string | null>(null);

  function copy(label: string, text: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(label);
      setTimeout(() => setCopied(null), 1500);
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold">{titre}</h2>
          <p className="text-xs text-[var(--muted)]">
            {current.source === "capture" ? "📷 Capture GMaps satellite" : "📁 Image importée"} ·{" "}
            {date}
            {current.lat != null && current.lng != null && (
              <>
                {" "}· {current.lat.toFixed(5)}, {current.lng.toFixed(5)}
              </>
            )}
          </p>
        </div>
        <button
          onClick={() => router.push("/analyse")}
          className="rounded-lg border border-[var(--border)] bg-white px-3 py-1.5 text-sm font-medium text-[var(--muted)] hover:bg-slate-50"
        >
          + Nouvelle analyse
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {/* Image analysée */}
        <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-white">
          {current.image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={current.image_url}
              alt={titre}
              className="block w-full"
            />
          ) : (
            <div className="p-6 text-sm text-[var(--muted)]">
              Image indisponible (lien expiré ou supprimée).
            </div>
          )}
        </div>

        {/* Synthèse + entreprises */}
        <div className="space-y-4">
          {r.resume && (
            <div className="rounded-xl border border-[var(--brand)]/30 bg-[var(--brand)]/5 p-4">
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--brand)]">
                Synthèse Magellan
              </h3>
              <p className="text-sm leading-relaxed text-slate-800">{r.resume}</p>
            </div>
          )}

          {r.entreprises && r.entreprises.length > 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-white p-4">
              <h3 className="mb-2 text-sm font-semibold">Entreprises identifiées</h3>
              <ul className="space-y-2">
                {r.entreprises.map((e, i) => (
                  <li key={i} className="text-sm">
                    <span className="font-medium">{e.nom}</span>
                    {e.secteur && (
                      <span className="text-[var(--muted)]"> · {e.secteur}</span>
                    )}
                    {e.indices && (
                      <p className="text-xs italic text-[var(--muted)]">{e.indices}</p>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* Terrain */}
      {r.terrain && (
        <div className="rounded-xl border border-[var(--border)] bg-white p-4">
          <h3 className="mb-3 text-sm font-semibold">Terrain</h3>
          <div className="grid gap-3 text-sm sm:grid-cols-3">
            <Fait
              titre="🏠 Toiture"
              lignes={[
                r.terrain.toiture?.surface_m2_estimee
                  ? `~${Math.round(r.terrain.toiture.surface_m2_estimee).toLocaleString("fr-FR")} m²`
                  : null,
                r.terrain.toiture?.type ?? null,
                r.terrain.toiture?.notes ?? null,
              ]}
            />
            <Fait
              titre="🅿️ Parking"
              lignes={[
                r.terrain.parking?.surface_m2_estimee
                  ? `~${Math.round(r.terrain.parking.surface_m2_estimee).toLocaleString("fr-FR")} m²`
                  : null,
                r.terrain.parking?.nb_places_estimee
                  ? `~${r.terrain.parking.nb_places_estimee} places`
                  : null,
                r.terrain.parking?.ombrieres_existantes === true
                  ? "Ombrières déjà présentes"
                  : r.terrain.parking?.ombrieres_existantes === false
                    ? "Pas d'ombrières (opportunité)"
                    : null,
              ]}
            />
            <Fait
              titre="🔌 Bornes VE"
              lignes={[
                r.terrain.bornes_ve?.presentes === true
                  ? `Présentes${r.terrain.bornes_ve.nb_estime ? ` (~${r.terrain.bornes_ve.nb_estime})` : ""}`
                  : r.terrain.bornes_ve?.presentes === false
                    ? "Aucune visible"
                    : "Indéterminé",
              ]}
            />
          </div>
          {r.terrain.autres && (
            <p className="mt-3 text-xs text-[var(--muted)]">
              <strong>Autres :</strong> {r.terrain.autres}
            </p>
          )}
        </div>
      )}

      {/* Opportunités */}
      {r.opportunites && r.opportunites.length > 0 && (
        <div className="rounded-xl border border-[var(--border)] bg-white p-4">
          <h3 className="mb-2 text-sm font-semibold">Opportunités commerciales</h3>
          <ul className="space-y-2">
            {r.opportunites.map((o, i) => (
              <li key={i} className="flex items-start gap-3 text-sm">
                <span
                  className={`mt-0.5 inline-block rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                    o.priorite === "haute"
                      ? "bg-red-100 text-red-700"
                      : o.priorite === "moyenne"
                        ? "bg-amber-100 text-amber-700"
                        : "bg-slate-100 text-slate-700"
                  }`}
                >
                  {o.priorite}
                </span>
                <div>
                  <div className="font-medium">{o.angle}</div>
                  <p className="text-[var(--muted)]">{o.pourquoi}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Accroche prête à copier */}
      {r.accroche && (
        <div className="rounded-xl border border-[var(--border)] bg-white p-4">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold">✉️ Accroche commerciale proposée</h3>
            <div className="flex gap-2">
              <button
                onClick={() => copy("sujet", r.accroche?.sujet ?? "")}
                className="rounded-md px-2 py-1 text-xs text-[var(--muted)] hover:bg-slate-100"
              >
                {copied === "sujet" ? "✓ Copié" : "📋 Sujet"}
              </button>
              <button
                onClick={() => copy("corps", r.accroche?.corps ?? "")}
                className="rounded-md px-2 py-1 text-xs text-[var(--muted)] hover:bg-slate-100"
              >
                {copied === "corps" ? "✓ Copié" : "📋 Corps"}
              </button>
            </div>
          </div>
          <p className="mb-2 text-sm font-medium">{r.accroche.sujet}</p>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
            {r.accroche.corps}
          </p>
        </div>
      )}
    </div>
  );
}

function Fait({ titre, lignes }: { titre: string; lignes: Array<string | null> }) {
  const items = lignes.filter((x): x is string => !!x);
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <p className="mb-1 text-xs font-semibold">{titre}</p>
      {items.length === 0 ? (
        <p className="text-xs text-[var(--muted)]">—</p>
      ) : (
        <ul className="space-y-0.5 text-sm">
          {items.map((x, i) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
