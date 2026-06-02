"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { addLeadNote } from "@/lib/actions/leads";

export function LeadNotes({ leadId }: { leadId: string }) {
  const router = useRouter();
  const [text, setText] = useState("");
  const [pending, startTransition] = useTransition();

  function save() {
    const t = text.trim();
    if (!t || pending) return;
    startTransition(async () => {
      const res = await addLeadNote(leadId, t);
      if (!res.error) {
        setText("");
        router.refresh();
      }
    });
  }

  return (
    <div className="mb-3">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Ajouter une note (appel, échange, contexte…)"
        rows={2}
        className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
      />
      <button
        onClick={save}
        disabled={pending || !text.trim()}
        className="mt-1.5 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium hover:bg-slate-50 disabled:opacity-40"
      >
        {pending ? "Ajout…" : "Ajouter la note"}
      </button>
    </div>
  );
}
