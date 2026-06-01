"use client";

import { useMemo, useState, useTransition } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { Lead } from "@/lib/database.types";
import { LEAD_STATUS_COLOR, LEAD_STATUS_LABEL, scoreColor } from "@/lib/ui";
import { setLeadsStatus } from "@/lib/actions/leads";

type SortKey = "entreprise" | "ville" | "effectif" | "score";

function effectifNum(e: string | null): number {
  if (!e) return -1;
  const m = e.match(/\d+/);
  return m ? parseInt(m[0], 10) : -1;
}

export function LeadsTable({ leads }: { leads: Lead[] }) {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [scoreMin, setScoreMin] = useState(0);
  const [onlyEmail, setOnlyEmail] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [pending, startTransition] = useTransition();
  const [msg, setMsg] = useState<string | null>(null);

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    const filtered = leads.filter((l) => {
      if (q && !l.entreprise.toLowerCase().includes(q)) return false;
      if (scoreMin && (l.score ?? 0) < scoreMin) return false;
      if (onlyEmail && !l.contact_email) return false;
      return true;
    });
    const dir = sortDir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => {
      let x: number | string;
      let y: number | string;
      if (sortKey === "score") {
        x = a.score ?? -1;
        y = b.score ?? -1;
      } else if (sortKey === "effectif") {
        x = effectifNum(a.effectif);
        y = effectifNum(b.effectif);
      } else {
        x = (a[sortKey] ?? "").toString().toLowerCase();
        y = (b[sortKey] ?? "").toString().toLowerCase();
      }
      if (x < y) return -1 * dir;
      if (x > y) return 1 * dir;
      return 0;
    });
  }, [leads, search, scoreMin, onlyEmail, sortKey, sortDir]);

  const allSelected = rows.length > 0 && rows.every((l) => selected.has(l.id));

  function toggle(id: string) {
    setSelected((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  }
  function toggleAll() {
    setSelected(allSelected ? new Set() : new Set(rows.map((l) => l.id)));
  }
  function sortBy(key: SortKey) {
    if (key === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir(key === "score" ? "desc" : "asc");
    }
  }

  function bulk(statut: "valide" | "ecarte", label: string) {
    const ids = [...selected];
    if (!ids.length) return;
    setMsg(null);
    startTransition(async () => {
      const res = await setLeadsStatus(ids, statut);
      if (res.error) setMsg(`❌ ${res.error}`);
      else {
        setMsg(`✅ ${ids.length} prospect(s) — ${label}`);
        setSelected(new Set());
        router.refresh();
      }
    });
  }

  const arrow = (key: SortKey) =>
    sortKey === key ? (sortDir === "asc" ? " ↑" : " ↓") : "";

  return (
    <div>
      {/* Barre de filtres */}
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Rechercher une entreprise…"
          className="w-56 rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm outline-none focus:border-[var(--brand)]"
        />
        <select
          value={scoreMin}
          onChange={(e) => setScoreMin(Number(e.target.value))}
          className="rounded-lg border border-[var(--border)] px-2 py-1.5 text-sm"
        >
          <option value={0}>Tous les scores</option>
          <option value={50}>Score ≥ 50</option>
          <option value={75}>Top leads (≥ 75)</option>
        </select>
        <label className="flex items-center gap-1.5 text-sm text-[var(--muted)]">
          <input
            type="checkbox"
            checked={onlyEmail}
            onChange={(e) => setOnlyEmail(e.target.checked)}
          />
          Avec email
        </label>
        <span className="ml-auto text-sm text-[var(--muted)]">
          {rows.length} prospect(s)
        </span>
      </div>

      {/* Barre d'actions groupées */}
      {selected.size > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-3 rounded-lg border border-[var(--brand)] bg-blue-50/50 px-3 py-2 text-sm">
          <span className="font-medium">{selected.size} sélectionné(s)</span>
          <button
            disabled={pending}
            onClick={() => bulk("valide", "validés")}
            className="rounded-md bg-[var(--brand)] px-3 py-1 font-medium text-white disabled:opacity-50"
          >
            Valider
          </button>
          <button
            disabled={pending}
            onClick={() => bulk("ecarte", "écartés")}
            className="rounded-md border border-[var(--border)] px-3 py-1 font-medium hover:bg-white disabled:opacity-50"
          >
            Écarter
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="text-[var(--muted)] hover:underline"
          >
            Annuler
          </button>
          {msg && <span>{msg}</span>}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-white">
        <table className="w-full text-sm">
          <thead className="border-b border-[var(--border)] bg-slate-50 text-left text-xs uppercase tracking-wide text-[var(--muted)]">
            <tr>
              <th className="w-10 px-4 py-3">
                <input type="checkbox" checked={allSelected} onChange={toggleAll} />
              </th>
              <Th onClick={() => sortBy("entreprise")}>Entreprise{arrow("entreprise")}</Th>
              <Th onClick={() => sortBy("ville")}>Ville{arrow("ville")}</Th>
              <Th onClick={() => sortBy("effectif")}>Effectif{arrow("effectif")}</Th>
              <th className="px-4 py-3">Contact</th>
              <Th onClick={() => sortBy("score")}>Score{arrow("score")}</Th>
              <th className="px-4 py-3">Statut</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((lead) => (
              <tr
                key={lead.id}
                className={`border-b border-[var(--border)] last:border-0 hover:bg-slate-50 ${
                  selected.has(lead.id) ? "bg-blue-50/40" : ""
                }`}
              >
                <td className="px-4 py-3">
                  <input
                    type="checkbox"
                    checked={selected.has(lead.id)}
                    onChange={() => toggle(lead.id)}
                  />
                </td>
                <td className="px-4 py-3">
                  <Link
                    href={`/leads/${lead.id}`}
                    className="font-medium hover:text-[var(--brand)]"
                  >
                    {lead.entreprise}
                  </Link>
                  {lead.libelle_naf && (
                    <div className="text-xs text-[var(--muted)]">{lead.libelle_naf}</div>
                  )}
                </td>
                <td className="px-4 py-3 text-[var(--muted)]">{lead.ville ?? "—"}</td>
                <td className="px-4 py-3 text-[var(--muted)]">{lead.effectif ?? "—"}</td>
                <td className="px-4 py-3">
                  {lead.contact_email ? (
                    <span className="text-emerald-600" title={lead.contact_email}>
                      ✓ email
                    </span>
                  ) : (
                    <span className="text-[var(--muted)]">—</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-block rounded-md px-2 py-0.5 text-xs font-semibold ${scoreColor(lead.score)}`}
                    >
                      {lead.score ?? "—"}
                    </span>
                    <span className="h-1.5 w-12 overflow-hidden rounded-full bg-slate-100">
                      <span
                        className={`block h-full ${
                          (lead.score ?? 0) >= 75
                            ? "bg-emerald-500"
                            : (lead.score ?? 0) >= 50
                              ? "bg-amber-500"
                              : "bg-slate-400"
                        }`}
                        style={{ width: `${Math.max(0, Math.min(100, lead.score ?? 0))}%` }}
                      />
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${LEAD_STATUS_COLOR[lead.statut]}`}
                  >
                    {LEAD_STATUS_LABEL[lead.statut]}
                  </span>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-[var(--muted)]">
                  Aucun prospect ne correspond aux filtres.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Th({
  children,
  onClick,
}: {
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <th
      onClick={onClick}
      className="cursor-pointer select-none px-4 py-3 hover:text-[var(--brand)]"
    >
      {children}
    </th>
  );
}
