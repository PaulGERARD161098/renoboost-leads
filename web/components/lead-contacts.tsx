"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  ajouterContact,
  definirPrincipal,
  supprimerContact,
} from "@/lib/actions/contacts";

export type LeadContactRow = {
  id: string;
  nom: string;
  role: string | null;
  email: string | null;
  tel: string | null;
  principal: boolean;
};

const ROLE_LABEL: Record<string, string> = {
  dg: "Dirigeant",
  daf: "DAF / Finance",
  energie: "Énergie / Maintenance",
  autre: "Autre",
};

/**
 * Interlocuteurs du lead : sur une PME de 100+ personnes, le bon contact
 * dépend du discours. Le « principal » est recopié dans leads.contact_* et
 * son rôle adapte le ton du brouillon (DAF → ROI, DG → stratégie…).
 */
export function LeadContacts({
  leadId,
  contacts,
}: {
  leadId: string;
  contacts: LeadContactRow[];
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [ouvert, setOuvert] = useState(false);
  const [nom, setNom] = useState("");
  const [role, setRole] = useState("dg");
  const [email, setEmail] = useState("");
  const [tel, setTel] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  function go(fn: () => Promise<{ error?: string }>) {
    setMsg(null);
    startTransition(async () => {
      const res = await fn();
      if (res.error) setMsg(`❌ ${res.error}`);
      else router.refresh();
    });
  }

  function ajouter() {
    go(async () => {
      const res = await ajouterContact(leadId, { nom, role, email, tel });
      if (!res.error) {
        setNom("");
        setEmail("");
        setTel("");
        setOuvert(false);
      }
      return res;
    });
  }

  return (
    <div className="rounded-xl border border-[var(--border)] bg-white p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
          Interlocuteurs ({contacts.length})
        </h2>
        <button
          onClick={() => setOuvert(!ouvert)}
          className="rounded-md border border-[var(--border)] px-2 py-1 text-xs font-medium hover:bg-slate-50"
        >
          {ouvert ? "Fermer" : "+ Ajouter"}
        </button>
      </div>

      {ouvert && (
        <div className="mb-3 grid gap-2 rounded-lg bg-slate-50 p-3">
          <div className="grid gap-2 sm:grid-cols-2">
            <input
              value={nom}
              onChange={(e) => setNom(e.target.value)}
              placeholder="Nom *"
              className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm outline-none focus:border-[var(--brand)]"
            />
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="rounded-lg border border-[var(--border)] bg-white px-3 py-1.5 text-sm outline-none focus:border-[var(--brand)]"
            >
              <option value="dg">Dirigeant</option>
              <option value="daf">DAF / Finance</option>
              <option value="energie">Énergie / Maintenance</option>
              <option value="autre">Autre</option>
            </select>
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email"
              className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm outline-none focus:border-[var(--brand)]"
            />
            <input
              value={tel}
              onChange={(e) => setTel(e.target.value)}
              placeholder="Téléphone"
              className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm outline-none focus:border-[var(--brand)]"
            />
          </div>
          <button
            onClick={ajouter}
            disabled={pending || !nom.trim()}
            className="justify-self-start rounded-lg bg-[var(--brand)] px-3 py-1.5 text-sm font-medium text-white hover:bg-[var(--brand-dark)] disabled:opacity-40"
          >
            {pending ? "Ajout…" : "Ajouter"}
          </button>
        </div>
      )}

      {contacts.length === 0 ? (
        <p className="text-sm text-[var(--muted)]">
          Aucun interlocuteur listé — le contact de la carte « Décideur »
          ci-dessus reste utilisé tel quel.
        </p>
      ) : (
        <ul className="space-y-2">
          {contacts.map((c) => (
            <li
              key={c.id}
              className={`flex items-start justify-between gap-3 rounded-lg border p-2.5 text-sm ${
                c.principal
                  ? "border-[var(--brand)]/40 bg-[var(--brand)]/5"
                  : "border-[var(--border)]"
              }`}
            >
              <div className="min-w-0">
                <div className="font-medium">
                  {c.nom}
                  {c.role && (
                    <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                      {ROLE_LABEL[c.role] ?? c.role}
                    </span>
                  )}
                  {c.principal && (
                    <span className="ml-1 rounded-full bg-[var(--brand)]/10 px-2 py-0.5 text-[10px] font-semibold text-[var(--brand)]">
                      ★ principal
                    </span>
                  )}
                </div>
                <p className="truncate text-xs text-[var(--muted)]">
                  {[c.email, c.tel].filter(Boolean).join(" · ") || "—"}
                </p>
              </div>
              <div className="flex shrink-0 gap-1">
                {!c.principal && (
                  <button
                    disabled={pending}
                    onClick={() => go(() => definirPrincipal(leadId, c.id))}
                    className="rounded-md px-2 py-1 text-xs text-[var(--muted)] hover:bg-slate-100"
                    title="Le mail partira vers ce contact, ton adapté à son rôle"
                  >
                    ★ Principal
                  </button>
                )}
                <button
                  disabled={pending}
                  onClick={() => go(() => supprimerContact(leadId, c.id))}
                  className="rounded-md px-2 py-1 text-xs text-rose-600 hover:bg-rose-50"
                >
                  Suppr.
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {msg && <p className="mt-2 text-xs text-rose-600">{msg}</p>}
    </div>
  );
}
