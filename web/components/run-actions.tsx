"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { Run, RunQualite } from "@/lib/database.types";
import { deleteRun, updateRun } from "@/lib/actions/runs";

const QUALITES: { value: RunQualite; label: string }[] = [
  { value: "bonne", label: "Bonne" },
  { value: "moyenne", label: "Moyenne" },
  { value: "mauvaise", label: "Mauvaise" },
];

/**
 * Menu d'actions d'une recherche : relancer (pré-rempli), renommer/annoter,
 * archiver, noter la qualité, supprimer. Conçu pour vivre dans une cartouche
 * cliquable : tous les clics arrêtent la propagation.
 */
export function RunActions({ run }: { run: Run }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, startTransition] = useTransition();

  const stop = (e: React.MouseEvent) => e.stopPropagation();

  function act(fn: () => Promise<{ error?: string } | { ok: true }>) {
    setOpen(false);
    startTransition(async () => {
      const res = await fn();
      if (res && "error" in res && res.error) {
        window.alert(`Erreur : ${res.error}`);
      } else {
        router.refresh();
      }
    });
  }

  function relancer() {
    setOpen(false);
    router.push(`/recherche?from=${run.id}`);
  }

  function renommer() {
    const nom = window.prompt("Nom de la recherche :", run.nom ?? "");
    if (nom === null) return;
    act(() => updateRun(run.id, { nom }));
  }

  function annoter() {
    const note = window.prompt("Note :", run.note ?? "");
    if (note === null) return;
    act(() => updateRun(run.id, { note }));
  }

  function supprimer() {
    if (
      !window.confirm(
        "Supprimer cette recherche et tous ses prospects ? Action irréversible.",
      )
    )
      return;
    act(() => deleteRun(run.id));
  }

  return (
    <div className="relative" onClick={stop}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        disabled={pending}
        aria-label="Actions de la recherche"
        className="rounded-md px-2 py-0.5 text-[var(--muted)] hover:bg-slate-100 disabled:opacity-50"
      >
        ⋯
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-20 mt-1 w-52 overflow-hidden rounded-lg border border-[var(--border)] bg-white py-1 text-sm shadow-lg">
            <Item onClick={relancer}>↻ Relancer (pré-rempli)</Item>
            <Item onClick={renommer}>✎ Renommer</Item>
            <Item onClick={annoter}>📝 Note</Item>
            <Item
              onClick={() => act(() => updateRun(run.id, { archive: !run.archive }))}
            >
              {run.archive ? "↩ Désarchiver" : "📥 Archiver"}
            </Item>
            <div className="my-1 border-t border-[var(--border)]" />
            <div className="px-3 py-1 text-xs uppercase tracking-wide text-[var(--muted)]">
              Qualité de la moisson
            </div>
            <div className="flex gap-1 px-3 pb-1.5 pt-0.5">
              {QUALITES.map((q) => (
                <button
                  key={q.value}
                  type="button"
                  onClick={() =>
                    act(() =>
                      updateRun(run.id, {
                        qualite: run.qualite === q.value ? null : q.value,
                      }),
                    )
                  }
                  className={`flex-1 rounded-md border px-1.5 py-1 text-xs ${
                    run.qualite === q.value
                      ? "border-[var(--brand)] bg-blue-50 text-[var(--brand)]"
                      : "border-[var(--border)] text-[var(--muted)] hover:bg-slate-50"
                  }`}
                >
                  {q.label}
                </button>
              ))}
            </div>
            <div className="my-1 border-t border-[var(--border)]" />
            <Item onClick={supprimer} tone="text-red-600 hover:bg-red-50">
              🗑 Supprimer
            </Item>
          </div>
        </>
      )}
    </div>
  );
}

function Item({
  children,
  onClick,
  tone = "hover:bg-slate-50",
}: {
  children: React.ReactNode;
  onClick: () => void;
  tone?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`block w-full px-3 py-1.5 text-left ${tone}`}
    >
      {children}
    </button>
  );
}
