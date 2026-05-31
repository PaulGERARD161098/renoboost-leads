"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { Verticale } from "@/lib/database.types";
import {
  createVerticale,
  updateVerticale,
  type VerticaleInput,
} from "@/lib/actions/verticales";

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

function asNumber(value: unknown): string {
  return typeof value === "number" ? String(value) : "";
}

/** Édite une verticale existante (avec `verticale`) ou en crée une (sans). */
export function VerticaleForm({ verticale }: { verticale?: Verticale }) {
  const router = useRouter();
  const cfg = verticale?.config ?? {};

  const [nom, setNom] = useState(verticale?.nom ?? "");
  const [description, setDescription] = useState(verticale?.description ?? "");
  const [offre, setOffre] = useState((cfg.offre as string) ?? "");
  const [secteurs, setSecteurs] = useState(asStringArray(cfg.secteurs_naf).join(", "));
  const [effectifMin, setEffectifMin] = useState(asNumber(cfg.effectif_min));
  const [signaux, setSignaux] = useState(asStringArray(cfg.signaux).join(", "));
  const [active, setActive] = useState(verticale?.active ?? true);
  const [msg, setMsg] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function parseList(raw: string): string[] {
    return raw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    const input: VerticaleInput = {
      nom: nom.trim(),
      description: description.trim(),
      offre: offre.trim(),
      secteursNaf: parseList(secteurs),
      effectifMin: effectifMin ? Number(effectifMin) : null,
      signaux: parseList(signaux),
      active,
    };
    if (!input.nom) {
      setMsg("❌ Le nom est obligatoire.");
      return;
    }
    startTransition(async () => {
      if (verticale) {
        const res = await updateVerticale(verticale.id, input);
        if (res?.error) setMsg(`❌ ${res.error}`);
        else {
          setMsg("✅ Cible enregistrée.");
          router.refresh();
        }
      } else {
        // createVerticale redirige vers la fiche en cas de succès ; seul l'échec revient.
        const res = await createVerticale(input);
        if (res?.error) setMsg(`❌ ${res.error}`);
      }
    });
  }

  return (
    <form
      onSubmit={submit}
      className="max-w-2xl space-y-5 rounded-xl border border-[var(--border)] bg-white p-6"
    >
      <div>
        <label className="mb-1 block text-sm font-medium">Nom de la cible</label>
        <input
          value={nom}
          onChange={(e) => setNom(e.target.value)}
          placeholder="Ex. Solaire toitures PME (Hauts-de-France)"
          className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
        />
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium">Description</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
          placeholder="À qui s'adresse-t-on et pourquoi ?"
          className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
        />
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium">Offre proposée</label>
        <input
          value={offre}
          onChange={(e) => setOffre(e.target.value)}
          placeholder="Ex. Photovoltaïque en autoconsommation"
          className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium">
            Secteurs NAF ciblés
          </label>
          <input
            value={secteurs}
            onChange={(e) => setSecteurs(e.target.value)}
            placeholder="46, 47, 52, 25"
            className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
          />
          <p className="mt-1 text-xs text-[var(--muted)]">
            Codes ou préfixes NAF, séparés par des virgules.
          </p>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Effectif min.</label>
          <input
            type="number"
            value={effectifMin}
            onChange={(e) => setEffectifMin(e.target.value)}
            placeholder="50"
            className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
          />
        </div>
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium">
          Signaux recherchés
        </label>
        <input
          value={signaux}
          onChange={(e) => setSignaux(e.target.value)}
          placeholder="grande toiture, entrepôt, site logistique"
          className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
        />
        <p className="mt-1 text-xs text-[var(--muted)]">
          Mots-clés qui qualifient un bon prospect, séparés par des virgules.
        </p>
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={active}
          onChange={(e) => setActive(e.target.checked)}
          className="h-4 w-4"
        />
        Cible active (disponible dans Nouvelle recherche)
      </label>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={pending}
          className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--brand-dark)] disabled:opacity-50"
        >
          {pending ? "Enregistrement…" : verticale ? "Enregistrer" : "Créer la cible"}
        </button>
        <button
          type="button"
          onClick={() => router.push("/cibles")}
          className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-medium hover:bg-slate-50"
        >
          Annuler
        </button>
        {msg && <span className="text-sm">{msg}</span>}
      </div>
    </form>
  );
}
