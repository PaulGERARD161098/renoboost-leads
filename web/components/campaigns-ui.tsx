"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  createCampaign,
  launchCampaign,
  setCampaignStatus,
} from "@/lib/actions/campaigns";
import type { CampaignStatus } from "@/lib/database.types";

type Verticale = { id: string; nom: string };

/** Formulaire de création d'une campagne. */
export function CreateCampaignForm({ verticales }: { verticales: Verticale[] }) {
  const router = useRouter();
  const [nom, setNom] = useState("");
  const [verticaleId, setVerticaleId] = useState("");
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!nom.trim()) return;
    start(async () => {
      const res = await createCampaign(nom, verticaleId || null);
      if (res.error) setError(res.error);
      else {
        setNom("");
        setVerticaleId("");
        setError(null);
        router.refresh();
      }
    });
  }

  return (
    <form
      onSubmit={submit}
      className="flex flex-wrap items-end gap-3 rounded-xl border border-[var(--border)] bg-white p-4"
    >
      <div className="grow">
        <label className="mb-1 block text-xs font-medium text-[var(--muted)]">
          Nouvelle campagne
        </label>
        <input
          value={nom}
          onChange={(e) => setNom(e.target.value)}
          placeholder="Nom (ex. Solaire PME 59 — juin)"
          className="w-full rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm outline-none focus:border-[var(--brand)]"
        />
      </div>
      <select
        value={verticaleId}
        onChange={(e) => setVerticaleId(e.target.value)}
        className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm"
      >
        <option value="">Toutes verticales</option>
        {verticales.map((v) => (
          <option key={v.id} value={v.id}>
            {v.nom}
          </option>
        ))}
      </select>
      <button
        disabled={pending || !nom.trim()}
        className="rounded-lg bg-[var(--brand)] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40"
      >
        {pending ? "Création…" : "Créer"}
      </button>
      {error && <p className="w-full text-sm text-red-600">{error}</p>}
    </form>
  );
}

/** Boutons de pilotage d'une campagne (lancer / pause / reprendre / terminer). */
export function CampaignActions({
  id,
  statut,
  nbAEnvoyer,
}: {
  id: string;
  statut: CampaignStatus;
  nbAEnvoyer: number;
}) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [msg, setMsg] = useState<string | null>(null);

  function run(fn: () => Promise<{ error?: string; envoyes?: number; simulation?: boolean }>) {
    start(async () => {
      const res = await fn();
      if (res.error) setMsg(res.error);
      else {
        if (typeof res.envoyes === "number")
          setMsg(
            `${res.envoyes} envoi${res.envoyes > 1 ? "s" : ""}${
              res.simulation ? " (simulation)" : ""
            }`,
          );
        router.refresh();
      }
    });
  }

  return (
    <div className="flex items-center gap-2">
      {(statut === "brouillon" || statut === "pausee") && (
        <button
          disabled={pending}
          onClick={() => run(() => launchCampaign(id))}
          className="rounded-lg bg-[var(--brand)] px-3 py-1 text-xs font-medium text-white disabled:opacity-40"
        >
          {pending ? "…" : `Lancer (${nbAEnvoyer})`}
        </button>
      )}
      {statut === "active" && (
        <button
          disabled={pending}
          onClick={() => run(() => setCampaignStatus(id, "pausee"))}
          className="rounded-lg border border-[var(--border)] px-3 py-1 text-xs font-medium hover:bg-slate-50 disabled:opacity-40"
        >
          Pause
        </button>
      )}
      {statut !== "terminee" && (
        <button
          disabled={pending}
          onClick={() => run(() => setCampaignStatus(id, "terminee"))}
          className="rounded-lg border border-[var(--border)] px-3 py-1 text-xs font-medium text-[var(--muted)] hover:bg-slate-50 disabled:opacity-40"
        >
          Terminer
        </button>
      )}
      {msg && <span className="text-xs text-[var(--muted)]">{msg}</span>}
    </div>
  );
}
