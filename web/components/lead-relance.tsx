"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { planifierRelance } from "@/lib/actions/leads";

export function LeadRelance({
  leadId,
  relanceAt,
}: {
  leadId: string;
  relanceAt: string | null;
}) {
  const router = useRouter();
  const [date, setDate] = useState(relanceAt ? relanceAt.slice(0, 10) : "");
  const [pending, startTransition] = useTransition();
  const [msg, setMsg] = useState<string | null>(null);

  function set(value: string | null) {
    setMsg(null);
    startTransition(async () => {
      const res = await planifierRelance(leadId, value);
      if (res.error) setMsg(`❌ ${res.error}`);
      else router.refresh();
    });
  }

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <span className="text-xs uppercase tracking-wide text-[var(--muted)]">
        Relance le
      </span>
      <input
        type="date"
        value={date}
        onChange={(e) => setDate(e.target.value)}
        className="rounded-lg border border-[var(--border)] px-2 py-1 text-sm outline-none focus:border-[var(--brand)]"
      />
      <button
        disabled={pending || !date}
        onClick={() => set(date ? new Date(date).toISOString() : null)}
        className="rounded-lg border border-[var(--border)] px-3 py-1 text-xs font-medium hover:bg-slate-50 disabled:opacity-40"
      >
        Planifier
      </button>
      {relanceAt && (
        <button
          disabled={pending}
          onClick={() => {
            setDate("");
            set(null);
          }}
          className="text-xs text-[var(--muted)] hover:underline disabled:opacity-40"
        >
          Effacer
        </button>
      )}
      {msg && (
        <p role="alert" aria-live="polite" className="w-full text-xs text-red-600">
          {msg}
        </p>
      )}
    </div>
  );
}
