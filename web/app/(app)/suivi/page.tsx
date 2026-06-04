import { createClient } from "@/lib/supabase/server";
import type { Lead, LeadStatus } from "@/lib/database.types";
import { KanbanCard } from "@/components/kanban-card";
import { ActionsBand } from "@/components/actions-band";

export const dynamic = "force-dynamic";

const COLUMNS: { statut: LeadStatus; label: string }[] = [
  { statut: "valide", label: "À envoyer" },
  { statut: "envoye", label: "Envoyés" },
  { statut: "ouvert", label: "Ouverts" },
  { statut: "repondu", label: "Répondus" },
  { statut: "a_relancer", label: "À relancer" },
];

export default async function SuiviPage() {
  const supabase = await createClient();
  const { data } = await supabase
    .from("leads")
    .select("*")
    .order("score", { ascending: false, nullsFirst: false })
    .limit(500);

  const leads = (data as Lead[] | null) ?? [];
  const byStatus = (s: LeadStatus) => leads.filter((l) => l.statut === s);

  const sent = leads.filter((l) =>
    ["envoye", "ouvert", "repondu"].includes(l.statut),
  ).length;
  const opened = leads.filter((l) =>
    ["ouvert", "repondu"].includes(l.statut),
  ).length;
  const replied = byStatus("repondu").length;
  const bounced = leads.filter((l) => l.bounced_at).length;
  const aRelancer = byStatus("a_relancer").length;

  // Contexte → Actions (pattern agent-first) : prochaines actions du pipeline.
  const endOfDay = new Date();
  endOfDay.setHours(23, 59, 59, 999);
  const relancesDues = leads.filter(
    (l) =>
      l.relance_at &&
      new Date(l.relance_at) <= endOfDay &&
      !["ecarte", "repondu"].includes(l.statut),
  ).length;
  const suiviActions = [
    {
      label: "Réponses à traiter",
      href: "/inbox?statut=repondu",
      n: replied,
      hint: "Un prospect a répondu — enchaîne le suivi commercial.",
    },
    {
      label: "Relances dues",
      href: "/inbox?statut=a_relancer",
      n: relancesDues,
      hint: "Relances qui tombent aujourd'hui ou en retard.",
    },
    {
      label: "Prêts à envoyer",
      href: "/inbox?statut=valide",
      n: byStatus("valide").length,
      hint: "Leads validés, prêts pour l'envoi.",
    },
  ];

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">Suivi</h1>
      <p className="mb-5 text-sm text-[var(--muted)]">
        Pipeline d&apos;envoi et de réponses.
      </p>

      <ActionsBand source="suivi" actions={suiviActions} />

      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-5">
        <Stat label="Envoyés" value={sent} />
        <Stat
          label="Taux d'ouverture"
          value={sent ? `${Math.round((opened / sent) * 100)}%` : "—"}
        />
        <Stat
          label="Taux de réponse"
          value={sent ? `${Math.round((replied / sent) * 100)}%` : "—"}
        />
        <Stat label="À relancer" value={aRelancer} />
        <Stat
          label="Rebonds"
          value={sent ? `${bounced} (${Math.round((bounced / sent) * 100)}%)` : bounced}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-5">
        {COLUMNS.map((col) => {
          const items = byStatus(col.statut);
          return (
            <div key={col.statut} className="rounded-xl bg-slate-100/60 p-3">
              <div className="mb-2 flex items-center justify-between px-1">
                <h2 className="text-sm font-semibold">{col.label}</h2>
                <span className="text-xs text-[var(--muted)]">
                  {items.length}
                </span>
              </div>
              <div className="space-y-2">
                {items.map((lead) => (
                  <KanbanCard key={lead.id} lead={lead} />
                ))}
                {items.length === 0 && (
                  <p className="px-1 py-3 text-xs text-[var(--muted)]">Vide</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-white p-4">
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-sm text-[var(--muted)]">{label}</div>
    </div>
  );
}
