"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { regionDe } from "@/lib/departements";

type DeptStat = { departement: string; n: number };
type Pop = { code: string; nom: string; population: number };

// Radar d'opportunités : départements SOUS-équipés (peu de bornes par habitant)
// = zones de prospection à fort potentiel. Population via geo.api.gouv.fr.
export function BornesRadar({ depts }: { depts: DeptStat[] }) {
  const [pops, setPops] = useState<Record<string, Pop> | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("https://geo.api.gouv.fr/departements?fields=code,nom,population")
      .then((r) => r.json())
      .then((arr: Pop[]) => {
        if (cancelled) return;
        const m: Record<string, Pop> = {};
        for (const p of arr) m[p.code] = p;
        setPops(m);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const lignes = useMemo(() => {
    if (!pops) return [];
    return depts
      .filter((d) => pops[d.departement]?.population)
      .map((d) => {
        const p = pops[d.departement];
        const pour100k = (d.n / p.population) * 100000;
        return { ...d, nom: p.nom, pop: p.population, pour100k };
      })
      .sort((a, b) => a.pour100k - b.pour100k) // sous-équipés d'abord
      .slice(0, 12);
  }, [depts, pops]);

  if (!depts.length) return null;

  return (
    <div className="rounded-xl border border-[var(--border)] bg-white p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
        🎯 Radar d'opportunités — départements sous-équipés
      </h2>
      <p className="mb-3 text-xs text-[var(--muted)]">
        Faible densité de bornes par habitant = zone à fort potentiel encore peu équipée.
        Lance une recherche directement sur le territoire.
      </p>

      {!pops ? (
        <p className="text-sm text-[var(--muted)]">Calcul des densités…</p>
      ) : (
        <ul className="space-y-1.5 text-sm">
          {lignes.map((l) => (
            <li
              key={l.departement}
              className="flex items-center justify-between gap-3 border-b border-[var(--border)] py-1.5"
            >
              <span className="min-w-0">
                <span className="font-medium">
                  {l.nom} ({l.departement})
                </span>{" "}
                <span className="text-xs text-[var(--muted)]">{regionDe(l.departement)}</span>
              </span>
              <span className="flex shrink-0 items-center gap-3">
                <span className="text-xs text-[var(--muted)]">
                  {l.pour100k.toFixed(1)} / 100k hab · {l.n.toLocaleString("fr-FR")} bornes
                </span>
                <Link
                  href={`/recherche?dept=${l.departement}`}
                  className="rounded-lg bg-[var(--brand)] px-2.5 py-1 text-xs font-medium text-white hover:opacity-90"
                >
                  Lancer une recherche ici
                </Link>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
