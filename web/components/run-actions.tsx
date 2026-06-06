"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { Run, RunQualite } from "@/lib/database.types";
import { deleteRun, updateRun } from "@/lib/actions/runs";

const QUALITES: { value: RunQualite; label: string }[] = [
  { value: "bonne", label: "Bonne" },
  { value: "moyenne", label: "Moyenne" },
  { value: "mauvaise", label: "Mauvaise" },
];

// Dialogue ouvert : saisie (renommer/annoter), confirmation (supprimer) ou erreur.
type Dialog =
  | { kind: "renommer"; value: string }
  | { kind: "annoter"; value: string }
  | { kind: "supprimer" }
  | { kind: "erreur"; message: string }
  | null;

/**
 * Menu d'actions d'une recherche : relancer (pré-rempli), renommer/annoter,
 * archiver, noter la qualité, supprimer. Conçu pour vivre dans une cartouche
 * cliquable : tous les clics arrêtent la propagation. Les saisies/confirmations
 * passent par une modale React (pas de window.prompt/confirm).
 */
export function RunActions({ run }: { run: Run }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [pending, startTransition] = useTransition();

  const stop = (e: React.MouseEvent) => e.stopPropagation();

  function act(fn: () => Promise<{ error?: string } | { ok: true }>) {
    setOpen(false);
    setDialog(null);
    startTransition(async () => {
      const res = await fn();
      if (res && "error" in res && res.error) {
        setDialog({ kind: "erreur", message: res.error });
      } else {
        router.refresh();
      }
    });
  }

  function relancer() {
    setOpen(false);
    router.push(`/recherche?from=${run.id}`);
  }

  function ouvrir(d: Dialog) {
    setOpen(false);
    setDialog(d);
  }

  return (
    <div className="flex items-center gap-0.5" onClick={stop}>
      <button
        type="button"
        onClick={() => ouvrir({ kind: "supprimer" })}
        disabled={pending}
        aria-label="Supprimer la recherche"
        title="Supprimer la recherche et ses prospects"
        className="rounded-md px-2 py-0.5 text-[var(--muted)] hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
      >
        🗑
      </button>
      <div className="relative">
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
            <Item onClick={() => ouvrir({ kind: "renommer", value: run.nom ?? "" })}>
              ✎ Renommer
            </Item>
            <Item onClick={() => ouvrir({ kind: "annoter", value: run.note ?? "" })}>
              📝 Note
            </Item>
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
          </div>
        </>
      )}
      </div>

      {dialog?.kind === "renommer" && (
        <SaisieModal
          titre="Renommer la recherche"
          label="Nom de la recherche"
          valeur={dialog.value}
          onAnnuler={() => setDialog(null)}
          onValider={(v) => act(() => updateRun(run.id, { nom: v }))}
        />
      )}
      {dialog?.kind === "annoter" && (
        <SaisieModal
          titre="Note de la recherche"
          label="Note"
          valeur={dialog.value}
          onAnnuler={() => setDialog(null)}
          onValider={(v) => act(() => updateRun(run.id, { note: v }))}
        />
      )}
      {dialog?.kind === "supprimer" && (
        <ConfirmModal
          titre="Supprimer cette recherche ?"
          message="La recherche et tous ses prospects seront supprimés. Action irréversible."
          libelleConfirmer="Supprimer"
          danger
          onAnnuler={() => setDialog(null)}
          onConfirmer={() => act(() => deleteRun(run.id))}
        />
      )}
      {dialog?.kind === "erreur" && (
        <ConfirmModal
          titre="Erreur"
          message={dialog.message}
          libelleConfirmer="OK"
          onAnnuler={() => setDialog(null)}
          onConfirmer={() => setDialog(null)}
        />
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

/** Coquille de modale : overlay, centrage, fermeture à l'Échap, rôle ARIA. */
function ModalShell({
  children,
  onClose,
}: {
  children: React.ReactNode;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="w-full max-w-sm rounded-xl border border-[var(--border)] bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}

function SaisieModal({
  titre,
  label,
  valeur,
  onAnnuler,
  onValider,
}: {
  titre: string;
  label: string;
  valeur: string;
  onAnnuler: () => void;
  onValider: (v: string) => void;
}) {
  const [v, setV] = useState(valeur);
  return (
    <ModalShell onClose={onAnnuler}>
      <h2 className="mb-3 text-base font-semibold">{titre}</h2>
      <label className="mb-1 block text-sm font-medium">{label}</label>
      <input
        autoFocus
        value={v}
        onChange={(e) => setV(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") onValider(v.trim());
        }}
        className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
      />
      <div className="mt-4 flex justify-end gap-2">
        <button
          type="button"
          onClick={onAnnuler}
          className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm font-medium hover:bg-slate-50"
        >
          Annuler
        </button>
        <button
          type="button"
          onClick={() => onValider(v.trim())}
          className="rounded-lg bg-[var(--brand)] px-3 py-1.5 text-sm font-semibold text-white hover:bg-[var(--brand-dark)]"
        >
          Valider
        </button>
      </div>
    </ModalShell>
  );
}

function ConfirmModal({
  titre,
  message,
  libelleConfirmer,
  danger = false,
  onAnnuler,
  onConfirmer,
}: {
  titre: string;
  message: string;
  libelleConfirmer: string;
  danger?: boolean;
  onAnnuler: () => void;
  onConfirmer: () => void;
}) {
  return (
    <ModalShell onClose={onAnnuler}>
      <h2 className="mb-2 text-base font-semibold">{titre}</h2>
      <p className="text-sm text-[var(--muted)]">{message}</p>
      <div className="mt-4 flex justify-end gap-2">
        <button
          type="button"
          onClick={onAnnuler}
          className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm font-medium hover:bg-slate-50"
        >
          Annuler
        </button>
        <button
          type="button"
          autoFocus
          onClick={onConfirmer}
          className={`rounded-lg px-3 py-1.5 text-sm font-semibold text-white ${
            danger ? "bg-red-600 hover:bg-red-700" : "bg-[var(--brand)] hover:bg-[var(--brand-dark)]"
          }`}
        >
          {libelleConfirmer}
        </button>
      </div>
    </ModalShell>
  );
}
