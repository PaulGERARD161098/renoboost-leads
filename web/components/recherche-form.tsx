"use client";

import { useState, useTransition } from "react";
import { createRun } from "@/lib/actions/runs";
import type { Verticale } from "@/lib/database.types";

export function RechercheForm({ verticales }: { verticales: Verticale[] }) {
  const [verticaleId, setVerticaleId] = useState(verticales[0]?.id ?? "");
  const [mode, setMode] = useState<"departement" | "adresse">("departement");
  const [departement, setDepartement] = useState("59");
  const [adresse, setAdresse] = useState("");
  const [rayon, setRayon] = useState("10");
  const [effectifMin, setEffectifMin] = useState("50");
  const [budget, setBudget] = useState("50");
  const [msg, setMsg] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (mode === "adresse" && !adresse.trim()) {
      setMsg("❌ Renseigne une adresse (centre de la zone).");
      return;
    }
    setMsg(null);
    startTransition(async () => {
      const res = await createRun({
        verticaleId,
        departement: mode === "departement" ? departement : null,
        adresse: mode === "adresse" ? adresse : null,
        rayonKm: mode === "adresse" ? Number(rayon) || 10 : null,
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

      {/* Mode de zone */}
      <div>
        <label className="mb-1 block text-sm font-medium">Zone ciblée</label>
        <div className="flex gap-2">
          {(["departement", "adresse"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={`flex-1 rounded-lg border px-3 py-1.5 text-sm font-medium transition ${
                mode === m
                  ? "border-[var(--brand)] bg-[var(--brand)] text-white"
                  : "border-[var(--border)] text-[var(--muted)] hover:bg-slate-50"
              }`}
            >
              {m === "departement" ? "Par département" : "Autour d'une adresse"}
            </button>
          ))}
        </div>
      </div>

      {mode === "departement" ? (
        <div>
          <label className="mb-1 block text-sm font-medium">Département</label>
          <input
            value={departement}
            onChange={(e) => setDepartement(e.target.value)}
            placeholder="59"
            className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
          />
        </div>
      ) : (
        <div className="grid grid-cols-[1fr_auto] gap-4">
          <div>
            <label className="mb-1 block text-sm font-medium">
              Adresse (centre de la zone)
            </label>
            <input
              value={adresse}
              onChange={(e) => setAdresse(e.target.value)}
              placeholder="ex : Zone d'activité de Wambrechies, 59118"
              className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Rayon (km)</label>
            <input
              type="number"
              value={rayon}
              onChange={(e) => setRayon(e.target.value)}
              className="w-24 rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
            />
          </div>
        </div>
      )}

      <div>
        <label className="mb-1 block text-sm font-medium">Effectif min.</label>
        <input
          type="number"
          value={effectifMin}
          onChange={(e) => setEffectifMin(e.target.value)}
          className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
        />
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
