"use client";

import { useState, useTransition } from "react";
import { createRun } from "@/lib/actions/runs";
import type { Verticale } from "@/lib/database.types";

export function RechercheForm({ verticales }: { verticales: Verticale[] }) {
  const [verticaleId, setVerticaleId] = useState(verticales[0]?.id ?? "");
  const [departement, setDepartement] = useState("59");
  const [effectifMin, setEffectifMin] = useState("50");
  const [budget, setBudget] = useState("50");
  const [msg, setMsg] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    startTransition(async () => {
      const res = await createRun({
        verticaleId,
        departement,
        effectifMin: effectifMin ? Number(effectifMin) : null,
        budgetEur: budget ? Number(budget) : null,
      });
      if (res.error) setMsg(`❌ ${res.error}`);
      else
        setMsg(
          "✅ Recherche demandée. Le moteur la traitera ; les prospects apparaîtront dans Prospects.",
        );
    });
  }

  return (
    <form
      onSubmit={submit}
      className="max-w-lg space-y-4 rounded-xl border border-[var(--border)] bg-white p-6"
    >
      <div>
        <label className="mb-1 block text-sm font-medium">Cible</label>
        <select
          value={verticaleId}
          onChange={(e) => setVerticaleId(e.target.value)}
          className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
        >
          {verticales.map((v) => (
            <option key={v.id} value={v.id}>
              {v.nom}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="mb-1 block text-sm font-medium">Département</label>
          <input
            value={departement}
            onChange={(e) => setDepartement(e.target.value)}
            className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">
            Effectif min.
          </label>
          <input
            type="number"
            value={effectifMin}
            onChange={(e) => setEffectifMin(e.target.value)}
            className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
          />
        </div>
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium">
          Budget plafond (€)
        </label>
        <input
          type="number"
          value={budget}
          onChange={(e) => setBudget(e.target.value)}
          className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
        />
      </div>

      <button
        type="submit"
        disabled={pending || !verticaleId}
        className="w-full rounded-lg bg-[var(--brand)] py-2.5 text-sm font-semibold text-white hover:bg-[var(--brand-dark)] disabled:opacity-50"
      >
        {pending ? "Envoi…" : "Lancer la recherche"}
      </button>
      {msg && <p className="text-sm">{msg}</p>}
    </form>
  );
}
