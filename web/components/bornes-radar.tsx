"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { regionDe } from "@/lib/departements";
import { croiserRadarPotentiel } from "@/lib/bornes-radar";

type DeptStat = { departement: string; n: number };
type Pop = { code: string; nom: string; population: number };

// Radar d'opportunités : croise les départements SOUS-équipés (peu de bornes par
// habitant = marché ouvert) avec NOTRE pipeline (prospects déjà identifiés sur le
// territoire = demande). Sous-équipé ET pipeline = priorité d'action. Population
// via geo.api.gouv.fr.
export function BornesRadar({
  depts,
  leadsParDept,
}: {
  depts: DeptStat[];
  leadsParDept: Record<string, number>;
}) {
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
    const base = depts
      .filter((d) => pops[d.departement]?.population)
      .map((d) => {
        const p = pops[d.departement];
        return {
          departement: d.departement,
          nom: p.nom,
          n: d.n,
          pour100k: (d.n / p.population) * 100000,
        };
      });
    return croiserRadarPotentiel(base, leadsParDept);
  }, [depts, pops, leadsParDept]);

  const nbPriorites = useMemo(() => lignes.filter((l) => l.priorite).length, [lignes]);

  if (!depts.length) return null;

  return (
    <div className="rounded-xl border border-[var(--border)] bg-white p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
        🎯 Radar d'opportunités — sous-équipement × pipeline
      </h2>
      <p className="mb-3 text-xs text-[var(--muted)]">
        Faible densité de bornes/habitant = marché ouvert. Croisé avec vos prospects
        déjà sur le territoire (★) : sous-équipé <strong>et</strong> pipeline existant =
        priorité, foncez.
      </p>

      {nbPriorites > 0 && (
        <p className="mb-3 rounded-lg bg-[var(--brand)]/10 px-3 py-2 text-xs text-[var(--brand)]">
          ★ {nbPriorites} département{nbPriorites > 1 ? "s" : ""} sous-équipé
          {nbPriorites > 1 ? "s" : ""} où vous avez déjà des prospects — à activer en
          priorité.
        </p>
      )}

      {!pops ? (
        <p className="text-sm text-[var(--muted)]">Calcul des densités…</p>
      ) : (
        <ul className="space-y-1.5 text-sm">
          {lignes.map((l) => (
            <li
              key={l.departement}
              className={`flex items-center justify-between gap-3 border-b border-[var(--border)] py-1.5 ${
                l.priorite ? "-mx-2 rounded-lg bg-[var(--brand)]/5 px-2" : ""
              }`}
            >
              <span className="min-w-0">
                <span className="font-medium">
                  {l.priorite && "★ "}
                  {l.nom} ({l.departement})
                </span>{" "}
                <span className="text-xs text-[var(--muted)]">{regionDe(l.departement)}</span>
                {l.pipeline > 0 && (
                  <span className="ml-1.5 rounded bg-[var(--brand)]/10 px-1.5 py-0.5 text-xs font-medium text-[var(--brand)]">
                    {l.pipeline} prospect{l.pipeline > 1 ? "s" : ""}
                  </span>
                )}
              </span>
              <span className="flex shrink-0 items-center gap-3">
                <span className="text-xs text-[var(--muted)]">
                  {l.pour100k.toFixed(1)} / 100k hab · {l.n.toLocaleString("fr-FR")} bornes
                </span>
                <Link
                  href={`/bornes?veille=${l.departement}#veille-ve`}
                  className="rounded-lg border border-[var(--brand)] px-2.5 py-1 text-xs font-medium text-[var(--brand)] hover:bg-[var(--brand)]/5"
                  title="Chercher la demande VE (flotte, ombrières) sur ce territoire"
                >
                  🛰️ Veille VE ici
                </Link>
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
