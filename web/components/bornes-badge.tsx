import type { ProximiteBornes } from "@/lib/bornes";

// Affiche l'équipement VE autour d'un lead. Composant serveur (présentation).
export function BornesBadge({
  prox,
  hasLocation,
}: {
  prox: ProximiteBornes | null;
  hasLocation: boolean;
}) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-white p-5">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
        Bornes de recharge VE (proximité)
      </h2>

      {!hasLocation ? (
        <p className="text-sm text-[var(--muted)]">
          Localisation requise — lance d’abord l’analyse satellite (elle géocode l’adresse),
          puis l’équipement VE autour du site s’affichera.
        </p>
      ) : !prox || prox.rayon === 0 ? (
        <p className="text-sm text-[var(--muted)]">
          Aucune borne connue dans un rayon de {prox?.rayon_km ?? 10} km
          {prox ? "" : " (données IRVE peut-être pas encore ingérées)"}. Prospect a priori
          non équipé.
        </p>
      ) : (
        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-3 gap-2 text-center">
            <Stat
              n={prox.sur_site}
              label="Sur site (<150 m)"
              tone={prox.sur_site > 0 ? "warn" : "ok"}
            />
            <Stat n={prox.voisinage} label="Voisinage (<500 m)" />
            <Stat n={prox.rayon} label={`Dans ${prox.rayon_km} km`} />
          </div>
          <ul className="space-y-1 text-[var(--muted)]">
            <li>
              📍 Borne la plus proche :{" "}
              {prox.plus_proche_km != null ? `${prox.plus_proche_km} km` : "—"}
            </li>
            {prox.dont_rossini > 0 && (
              <li className="font-medium text-[var(--brand)]">
                ⚡ Dont {prox.dont_rossini} posée(s) par Rossini Energy
              </li>
            )}
            {prox.operateurs.length > 0 && (
              <li>
                Opérateurs : {prox.operateurs.map((o) => `${o.nom} (${o.n})`).join(" · ")}
              </li>
            )}
          </ul>
          <p className="text-xs text-[var(--muted)]">
            {prox.sur_site > 0
              ? "Probablement déjà équipé sur site."
              : prox.rayon > 0
                ? "Non équipé sur site, mais la zone s’équipe — signal d’intention."
                : ""}
          </p>
        </div>
      )}
    </div>
  );
}

function Stat({
  n,
  label,
  tone = "neutral",
}: {
  n: number;
  label: string;
  tone?: "neutral" | "ok" | "warn";
}) {
  const color =
    tone === "warn" && n > 0
      ? "text-amber-700"
      : tone === "ok"
        ? "text-slate-900"
        : "text-slate-900";
  return (
    <div className="rounded-lg bg-slate-50 px-2 py-2">
      <div className={`text-lg font-bold ${color}`}>{n}</div>
      <div className="text-xs text-[var(--muted)]">{label}</div>
    </div>
  );
}
