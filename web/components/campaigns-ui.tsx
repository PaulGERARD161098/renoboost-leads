"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  createCampaign,
  launchCampaign,
  setCampaignClient,
  setCampaignStatus,
} from "@/lib/actions/campaigns";
import type { CampaignStatus } from "@/lib/database.types";

type Verticale = { id: string; nom: string };

/** Formulaire de création d'une campagne. */
export function CreateCampaignForm({ verticales }: { verticales: Verticale[] }) {
  const router = useRouter();
  const [nom, setNom] = useState("");
  const [verticaleId, setVerticaleId] = useState("");
  const [client, setClient] = useState("");
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!nom.trim()) return;
    start(async () => {
      const res = await createCampaign(nom, verticaleId || null, client || null);
      if (res.error) setError(res.error);
      else {
        setNom("");
        setVerticaleId("");
        setClient("");
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
      <div>
        <label className="mb-1 block text-xs font-medium text-[var(--muted)]">
          Client
        </label>
        <input
          value={client}
          onChange={(e) => setClient(e.target.value)}
          placeholder="Ex. Rossini Energy"
          className="w-44 rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm outline-none focus:border-[var(--brand)]"
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

/**
 * Affecte / modifie le client d'une campagne en inline. Les mails auto-générés
 * pour les leads de la campagne sont signés au nom de ce client.
 */
export function CampaignClient({
  id,
  clientNom,
}: {
  id: string;
  clientNom: string | null;
}) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(clientNom ?? "");
  const [pending, start] = useTransition();

  function save() {
    start(async () => {
      const res = await setCampaignClient(id, val);
      if (!res.error) {
        setEditing(false);
        router.refresh();
      }
    });
  }

  if (!editing) {
    return (
      <button
        onClick={() => {
          setVal(clientNom ?? "");
          setEditing(true);
        }}
        className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 hover:bg-slate-200"
        title="Affecter cette campagne à un client (signe les mails à son nom)"
      >
        {clientNom ? `Client : ${clientNom}` : "+ Affecter un client"}
      </button>
    );
  }

  return (
    <span className="inline-flex items-center gap-1">
      <input
        value={val}
        autoFocus
        onChange={(e) => setVal(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") save();
          if (e.key === "Escape") setEditing(false);
        }}
        placeholder="Nom du client"
        className="w-40 rounded-lg border border-[var(--border)] px-2 py-0.5 text-xs outline-none focus:border-[var(--brand)]"
      />
      <button
        disabled={pending}
        onClick={save}
        className="rounded-lg bg-[var(--brand)] px-2 py-0.5 text-xs font-medium text-white disabled:opacity-40"
      >
        {pending ? "…" : "OK"}
      </button>
      <button
        onClick={() => setEditing(false)}
        className="rounded-lg px-1 py-0.5 text-xs text-[var(--muted)] hover:bg-slate-50"
      >
        Annuler
      </button>
    </span>
  );
}
