"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  chargerReferencesExemples,
  creerReference,
  supprimerReference,
  toggleReference,
} from "@/lib/actions/references";

export type ReferenceRow = {
  id: string;
  nom: string;
  ville: string | null;
  lat: number | null;
  axe: "solaire" | "ombrieres" | "bornes";
  description: string | null;
  actif: boolean;
};

const AXE_LABEL: Record<ReferenceRow["axe"], string> = {
  solaire: "🔆 Solaire",
  ombrieres: "🅿️ Ombrières",
  bornes: "🔌 Bornes",
};

/**
 * Admin des références chantiers (preuve sociale) : la plus proche du prospect
 * — sur l'axe du mail — est citée automatiquement dans les brouillons.
 */
export function ReferencesChantiers({ refs }: { refs: ReferenceRow[] }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [ouvert, setOuvert] = useState(false);
  const [nom, setNom] = useState("");
  const [ville, setVille] = useState("");
  const [axe, setAxe] = useState<ReferenceRow["axe"]>("ombrieres");
  const [description, setDescription] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  function ajouter() {
    setMsg(null);
    startTransition(async () => {
      const res = await creerReference({ nom, ville, axe, description });
      if (res.error) {
        setMsg(`❌ ${res.error}`);
        return;
      }
      setMsg(res.geocode ? null : "⚠️ Ville non géolocalisée — la référence sera citée sans distance.");
      setNom("");
      setVille("");
      setDescription("");
      router.refresh();
    });
  }

  function go(fn: () => Promise<{ error?: string }>) {
    setMsg(null);
    startTransition(async () => {
      const res = await fn();
      if (res.error) setMsg(`❌ ${res.error}`);
      else router.refresh();
    });
  }

  return (
    <section className="mt-8">
      <div className="mb-2 flex items-end justify-between">
        <div>
          <h2 className="text-lg font-bold">📍 Références chantiers</h2>
          <p className="text-sm text-[var(--muted)]">
            La référence la plus proche du prospect (même axe que le mail) est
            citée automatiquement dans les brouillons — preuve locale.
          </p>
        </div>
        <button
          onClick={() => setOuvert(!ouvert)}
          className="rounded-lg border border-[var(--border)] bg-white px-3 py-1.5 text-sm font-medium hover:bg-slate-50"
        >
          {ouvert ? "Fermer" : "+ Ajouter une référence"}
        </button>
      </div>

      {msg?.startsWith("❌") && (
        <p role="alert" aria-live="polite" className="mb-3 text-xs text-red-600">
          {msg}
        </p>
      )}

      {ouvert && (
        <div className="mb-3 grid gap-3 rounded-xl border border-[var(--border)] bg-white p-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--muted)]">Client / chantier *</label>
            <input
              value={nom}
              onChange={(e) => setNom(e.target.value)}
              placeholder="Ex. Brasserie du Pavé"
              className="w-full rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm outline-none focus:border-[var(--brand)]"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--muted)]">Ville</label>
            <input
              value={ville}
              onChange={(e) => setVille(e.target.value)}
              placeholder="Ex. Seclin"
              className="w-full rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm outline-none focus:border-[var(--brand)]"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--muted)]">Axe</label>
            <select
              value={axe}
              onChange={(e) => setAxe(e.target.value as ReferenceRow["axe"])}
              className="w-full rounded-lg border border-[var(--border)] bg-white px-3 py-1.5 text-sm outline-none focus:border-[var(--brand)]"
            >
              <option value="ombrieres">🅿️ Ombrières</option>
              <option value="bornes">🔌 Bornes VE</option>
              <option value="solaire">🔆 Solaire toiture</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--muted)]">Phrase citable</label>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Ex. 60 places d'ombrières bois, livrées en 2025"
              className="w-full rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm outline-none focus:border-[var(--brand)]"
            />
          </div>
          <div className="sm:col-span-2 lg:col-span-4">
            <button
              onClick={ajouter}
              disabled={pending || !nom.trim()}
              className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--brand-dark)] disabled:opacity-40"
            >
              {pending ? "Ajout…" : "Ajouter"}
            </button>
            {msg && <span className="ml-3 text-xs text-[var(--muted)]">{msg}</span>}
          </div>
        </div>
      )}

      {refs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-white p-4 text-sm text-[var(--muted)]">
          <p className="mb-3">
            Aucune référence pour l&apos;instant — ajoute tes premiers chantiers
            livrés : ils renforceront chaque mail envoyé dans leur zone. Pas encore
            de chantier à saisir ? Charge des exemples pour voir l&apos;effet tout de
            suite (supprimables à tout moment).
          </p>
          <button
            onClick={() =>
              go(async () => {
                const res = await chargerReferencesExemples();
                if (!res.error)
                  setMsg(`✅ ${res.ajoutes} exemple(s) ajouté(s) — à adapter ou remplacer.`);
                return res;
              })
            }
            disabled={pending}
            className="rounded-lg border border-[var(--brand)]/40 bg-[var(--brand)]/5 px-3 py-1.5 text-sm font-medium text-[var(--brand)] hover:bg-[var(--brand)]/10 disabled:opacity-40"
          >
            {pending ? "Chargement…" : "✨ Charger 4 exemples (Hauts-de-France)"}
          </button>
          {msg && <span className="ml-3 text-xs">{msg}</span>}
        </div>
      ) : (
        <ul className="grid gap-2 md:grid-cols-2">
          {refs.map((r) => (
            <li
              key={r.id}
              className={`flex items-start justify-between gap-3 rounded-xl border border-[var(--border)] bg-white p-3 text-sm ${
                r.actif ? "" : "opacity-50"
              }`}
            >
              <div className="min-w-0">
                <div className="font-medium">
                  {AXE_LABEL[r.axe]} · {r.nom}
                  {r.ville && <span className="text-[var(--muted)]"> — {r.ville}</span>}
                  {r.ville && r.lat == null && (
                    <span title="Ville non géolocalisée : citée sans distance"> ⚠️</span>
                  )}
                </div>
                {r.description && (
                  <p className="text-xs text-[var(--muted)]">{r.description}</p>
                )}
              </div>
              <div className="flex shrink-0 gap-1">
                <button
                  disabled={pending}
                  onClick={() => go(() => toggleReference(r.id, !r.actif))}
                  className="rounded-md px-2 py-1 text-xs text-[var(--muted)] hover:bg-slate-100"
                >
                  {r.actif ? "Désactiver" : "Activer"}
                </button>
                <button
                  disabled={pending}
                  onClick={() => go(() => supprimerReference(r.id))}
                  className="rounded-md px-2 py-1 text-xs text-rose-600 hover:bg-rose-50"
                >
                  Supprimer
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
