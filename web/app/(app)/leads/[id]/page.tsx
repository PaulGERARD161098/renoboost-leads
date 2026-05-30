import Link from "next/link";
import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import type { Lead, LeadEvent } from "@/lib/database.types";
import { LeadEditor } from "@/components/lead-editor";
import {
  LEAD_STATUS_COLOR,
  LEAD_STATUS_LABEL,
  formatDate,
  scoreColor,
} from "@/lib/ui";

export const dynamic = "force-dynamic";

const EVENT_LABEL: Record<string, string> = {
  cree: "Créé",
  envoye: "Email envoyé",
  ouvert: "Email ouvert",
  repondu: "Réponse reçue",
  relance: "Relancé",
  ecarte: "Écarté",
  note: "Note",
  oubli_rgpd: "Données effacées (RGPD)",
};

export default async function LeadPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createClient();

  const { data: lead } = await supabase
    .from("leads")
    .select("*")
    .eq("id", id)
    .single();

  if (!lead) notFound();
  const l = lead as Lead;

  const { data: events } = await supabase
    .from("lead_events")
    .select("*")
    .eq("lead_id", id)
    .order("at", { ascending: false });

  return (
    <div>
      <Link href="/inbox" className="text-sm text-[var(--muted)] hover:underline">
        ← Retour aux prospects
      </Link>

      <div className="mt-3 mb-5 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">{l.entreprise}</h1>
          <p className="text-sm text-[var(--muted)]">
            {l.libelle_naf ?? l.naf ?? "Secteur n.c."}
            {l.ville ? ` · ${l.ville}` : ""}
            {l.code_postal ? ` (${l.code_postal})` : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`rounded-md px-2 py-1 text-sm font-semibold ${scoreColor(l.score)}`}
          >
            Score {l.score ?? "—"}
          </span>
          <span
            className={`rounded-full px-3 py-1 text-sm font-medium ${LEAD_STATUS_COLOR[l.statut]}`}
          >
            {LEAD_STATUS_LABEL[l.statut]}
          </span>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <LeadEditor lead={l} />
        </div>

        <div className="space-y-5">
          <div className="rounded-xl border border-[var(--border)] bg-white p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
              Contact
            </h2>
            <dl className="space-y-2 text-sm">
              <Field label="Dirigeant" value={l.contact_nom} />
              <Field label="Email" value={l.contact_email} />
              <Field label="Téléphone" value={l.contact_tel} />
              <Field
                label="Site"
                value={l.site_web}
                href={l.site_web ?? undefined}
              />
              <Field label="Effectif" value={l.effectif} />
              <Field label="SIREN" value={l.siren} />
            </dl>
          </div>

          <div className="rounded-xl border border-[var(--border)] bg-white p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
              Activité
            </h2>
            <ul className="space-y-3 text-sm">
              {(events as LeadEvent[] | null)?.length ? (
                (events as LeadEvent[]).map((ev) => (
                  <li key={ev.id} className="flex justify-between gap-2">
                    <span>{EVENT_LABEL[ev.type] ?? ev.type}</span>
                    <span className="text-xs text-[var(--muted)]">
                      {formatDate(ev.at)}
                    </span>
                  </li>
                ))
              ) : (
                <li className="text-[var(--muted)]">Aucune activité.</li>
              )}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  href,
}: {
  label: string;
  value: string | null;
  href?: string;
}) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-[var(--muted)]">{label}</dt>
      <dd className="text-right font-medium">
        {value ? (
          href ? (
            <a
              href={href.startsWith("http") ? href : `https://${href}`}
              target="_blank"
              rel="noreferrer"
              className="text-[var(--brand)] hover:underline"
            >
              {value}
            </a>
          ) : (
            value
          )
        ) : (
          "—"
        )}
      </dd>
    </div>
  );
}
