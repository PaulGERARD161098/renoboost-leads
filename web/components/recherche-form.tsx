"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { createRun } from "@/lib/actions/runs";
import { createZoneCible, deleteZoneCible } from "@/lib/actions/zones";
import type { Verticale, ZoneCible } from "@/lib/database.types";

export type RechercheInitial = {
  verticaleId?: string;
  mode?: "departement" | "adresse";
  departement?: string;
  adresse?: string;
  rayon?: string;
  effectifMin?: string;
  budget?: string;
  isTest?: boolean;
};

export function RechercheForm({
  verticales,
  zones = [],
  initial,
}: {
  verticales: Verticale[];
  zones?: ZoneCible[];
  initial?: RechercheInitial;
}) {
  const router = useRouter();
  const [verticaleId, setVerticaleId] = useState(
    initial?.verticaleId ?? verticales[0]?.id ?? "",
  );
  const [mode, setMode] = useState<"departement" | "adresse">(
    initial?.mode ?? "departement",
  );
  const [departement, setDepartement] = useState(initial?.departement ?? "59");
  const [adresse, setAdresse] = useState(initial?.adresse ?? "");
  const [rayon, setRayon] = useState(initial?.rayon ?? "10");
  const [nomZone, setNomZone] = useState("");
  const [effectifMin, setEffectifMin] = useState(initial?.effectifMin ?? "50");
  const [budget, setBudget] = useState(initial?.budget ?? "50");
  const [isTest, setIsTest] = useState(initial?.isTest ?? false);
  const [msg, setMsg] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function appliquerZone(id: string) {
    const z = zones.find((x) => x.id === id);
    if (z) {
      setAdresse(z.adresse);
      setRayon(String(z.rayon_km));
    }
  }

  function enregistrerZone() {
    if (!adresse.trim() || !nomZone.trim()) {
      setMsg("❌ Donne un nom et une adresse pour enregistrer la zone.");
      return;
    }
    startTransition(async () => {
      const res = await createZoneCible({
        nom: nomZone,
        adresse,
        rayonKm: Number(rayon) || 10,
      });
      if (res.error) setMsg(`❌ ${res.error}`);
      else {
        setNomZone("");
        setMsg("✅ Zone enregistrée.");
        router.refresh();
      }
    });
  }

  function supprimerZone(id: string) {
    startTransition(async () => {
      await deleteZoneCible(id);
      router.refresh();
    });
  }

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
        isTest,
      });
      if (res.error) setMsg(`❌ ${res.error}`);
      else
        setMsg(
          isTest
            ? "✅ Recherche test demandée (mode démo, gratuit). Les faux prospects apparaîtront dans Prospects."
            : "✅ Recherche demandée. Le moteur la traitera ; les prospects apparaîtront dans Prospects.",
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
        <div className="space-y-3">
          {zones.length > 0 && (
            <div>
              <label className="mb-1 block text-sm font-medium">
                Zone enregistrée
              </label>
              <select
                defaultValue=""
                onChange={(e) => appliquerZone(e.target.value)}
                className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
              >
                <option value="">— Choisir une zone enregistrée —</option>
                {zones.map((z) => (
                  <option key={z.id} value={z.id}>
                    {z.nom} ({z.rayon_km} km)
                  </option>
                ))}
              </select>
            </div>
          )}
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
          {/* Enregistrer la zone */}
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <label className="mb-1 block text-xs text-[var(--muted)]">
                Enregistrer cette zone (nom)
              </label>
              <input
                value={nomZone}
                onChange={(e) => setNomZone(e.target.value)}
                placeholder="ex : ZA Wambrechies"
                className="w-full rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm"
              />
            </div>
            <button
              type="button"
              onClick={enregistrerZone}
              disabled={pending || !adresse.trim() || !nomZone.trim()}
              className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm font-medium hover:bg-slate-50 disabled:opacity-40"
            >
              💾 Enregistrer
            </button>
          </div>
          {zones.length > 0 && (
            <ul className="flex flex-wrap gap-1.5">
              {zones.map((z) => (
                <li
                  key={z.id}
                  className="flex items-center gap-1 rounded-full border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--muted)]"
                >
                  {z.nom}
                  <button
                    type="button"
                    onClick={() => supprimerZone(z.id)}
                    className="text-[var(--muted)] hover:text-red-600"
                    aria-label={`Supprimer ${z.nom}`}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
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

      <label className="flex items-start gap-2 rounded-lg border border-[var(--border)] bg-slate-50 p-3 text-sm">
        <input
          type="checkbox"
          checked={isTest}
          onChange={(e) => setIsTest(e.target.checked)}
          className="mt-0.5"
        />
        <span>
          <span className="font-medium">Recherche test (mode démo, gratuit)</span>
          <span className="block text-xs text-[var(--muted)]">
            Génère de faux prospects sans appel externe ni coût — pour essayer
            l&apos;interface.
          </span>
        </span>
      </label>

      <button
        type="submit"
        disabled={pending || !verticaleId}
        className={`w-full rounded-lg py-2.5 text-sm font-semibold text-white disabled:opacity-50 ${
          isTest
            ? "bg-violet-600 hover:bg-violet-700"
            : "bg-[var(--brand)] hover:bg-[var(--brand-dark)]"
        }`}
      >
        {pending
          ? "Envoi…"
          : isTest
            ? "Lancer la recherche test"
            : "Lancer la recherche"}
      </button>
      {msg && <p className="text-sm">{msg}</p>}
    </form>
  );
}
