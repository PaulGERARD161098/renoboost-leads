"use client";

import { useMemo, useState } from "react";
import { regionDe } from "@/lib/departements";

type DeptStat = { departement: string; n: number };

// Analyses bornes : filtre déroulant par département, Top 10, classement par
// région (total + département leader). Calculé côté client à partir du RPC.
export function BornesAnalytics({ depts }: { depts: DeptStat[] }) {
  const [sel, setSel] = useState<string>("");

  const total = useMemo(() => depts.reduce((s, d) => s + d.n, 0), [depts]);
  const tries = useMemo(() => [...depts].sort((a, b) => b.n - a.n), [depts]);
  const top10 = tries.slice(0, 10);
  const maxTop = top10[0]?.n ?? 1;

  const rangDe = (dept: string) => tries.findIndex((d) => d.departement === dept) + 1;
  const selStat = depts.find((d) => d.departement === sel) ?? null;

  // Agrégat par région : total + leader.
  const regions = useMemo(() => {
    const map = new Map<string, { total: number; leader: DeptStat | null }>();
    for (const d of depts) {
      const r = regionDe(d.departement);
      const cur = map.get(r) ?? { total: 0, leader: null };
      cur.total += d.n;
      if (!cur.leader || d.n > cur.leader.n) cur.leader = d;
      map.set(r, cur);
    }
    return [...map.entries()]
      .map(([region, v]) => ({ region, ...v }))
      .sort((a, b) => b.total - a.total);
  }, [depts]);

  if (!depts.length) {
    return (
      <p className="rounded-xl border border-dashed border-[var(--border)] bg-white p-6 text-center text-sm text-[var(--muted)]">
        Aucune donnée. Lance l’import IRVE ci-dessus.
      </p>
    );
  }

  return (
    <div className="space-y-5">
      {/* Filtre déroulant par département */}
      <div className="rounded-xl border border-[var(--border)] bg-white p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
          Rechercher un département
        </h2>
        <select
          value={sel}
          onChange={(e) => setSel(e.target.value)}
          className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm md:w-72"
        >
          <option value="">— Choisir un département —</option>
          {tries.map((d) => (
            <option key={d.departement} value={d.departement}>
              Dépt {d.departement} ({regionDe(d.departement)}) — {d.n.toLocaleString("fr-FR")}
            </option>
          ))}
        </select>
        {selStat && (
          <div className="mt-3 flex flex-wrap gap-4 text-sm">
            <span>
              <b>{selStat.n.toLocaleString("fr-FR")}</b> bornes
            </span>
            <span className="text-[var(--muted)]">{regionDe(selStat.departement)}</span>
            <span className="text-[var(--muted)]">
              Rang national : <b>#{rangDe(selStat.departement)}</b> / {depts.length}
            </span>
            <span className="text-[var(--muted)]">
              {((selStat.n / total) * 100).toFixed(1)} % du parc national
            </span>
          </div>
        )}
      </div>

      {/* Top 10 */}
      <div className="rounded-xl border border-[var(--border)] bg-white p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
          Top 10 départements
        </h2>
        <ul className="space-y-2">
          {top10.map((d, i) => (
            <li key={d.departement} className="flex items-center gap-3 text-sm">
              <span className="w-6 shrink-0 text-right font-medium text-[var(--muted)]">
                {i + 1}
              </span>
              <span className="w-28 shrink-0">
                Dépt {d.departement}{" "}
                <span className="text-xs text-[var(--muted)]">{regionDe(d.departement)}</span>
              </span>
              <span className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                <span
                  className="block h-full rounded-full bg-[var(--brand)]"
                  style={{ width: `${(d.n / maxTop) * 100}%` }}
                />
              </span>
              <span className="w-16 shrink-0 text-right font-medium">
                {d.n.toLocaleString("fr-FR")}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {/* Classement par région */}
      <div className="rounded-xl border border-[var(--border)] bg-white p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
          Classement par région
        </h2>
        <ul className="space-y-1 text-sm">
          {regions.map((r) => (
            <li
              key={r.region}
              className="flex items-center justify-between gap-2 border-b border-[var(--border)] py-1.5"
            >
              <span className="font-medium">{r.region}</span>
              <span className="flex items-center gap-3">
                {r.leader && (
                  <span className="text-xs text-[var(--muted)]">
                    leader : dépt {r.leader.departement} ({r.leader.n.toLocaleString("fr-FR")})
                  </span>
                )}
                <span className="w-20 text-right font-medium">
                  {r.total.toLocaleString("fr-FR")}
                </span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
