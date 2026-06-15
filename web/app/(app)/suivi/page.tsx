import { createClient } from "@/lib/supabase/server";
import type { Lead, LeadStatus } from "@/lib/database.types";
import { KanbanCard } from "@/components/kanban-card";
import { ActionsBand } from "@/components/actions-band";
import { rankBandActions } from "@/lib/suggestions";
import {
  statsParAngle,
  angleGagnantParCible,
  liftAngleAppris,
  ANGLE_LABEL,
} from "@/lib/stats-angles";

export const dynamic = "force-dynamic";

const COLUMNS: { statut: LeadStatus; label: string }[] = [
  { statut: "valide", label: "À envoyer" },
  { statut: "envoye", label: "Envoyés" },
  { statut: "ouvert", label: "Ouverts" },
  { statut: "repondu", label: "Répondus" },
  { statut: "a_relancer", label: "À relancer" },
  { statut: "rdv_pris", label: "RDV pris" },
  { statut: "gagne", label: "Gagnés 🏆" },
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
  // Le tunnel RDV inclut les leads déjà conclus (ils sont passés par le RDV).
  const gagnes = byStatus("gagne").length;
  const perdus = byStatus("perdu").length;
  const rdvPris = byStatus("rdv_pris").length + gagnes + perdus;
  // Base « contactés » = tout ce qui a quitté le stade « validé » (RDV inclus).
  const contactes = leads.filter((l) =>
    ["envoye", "ouvert", "repondu", "a_relancer", "rdv_pris", "gagne", "perdu"].includes(
      l.statut,
    ),
  ).length;

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
      label: "Appels à passer",
      href: "/inbox?call=a_appeler",
      n: leads.filter((l) => l.call_statut === "a_appeler").length,
      hint: "Mail épuisé — l'agent a basculé ces leads sur le canal téléphone.",
    },
    {
      label: "Prêts à envoyer",
      href: "/inbox?statut=valide",
      n: byStatus("valide").length,
      hint: "Leads validés, prêts pour l'envoi.",
    },
  ];
  const rankedActions = await rankBandActions(supabase, "suivi", suiviActions);

  // Quel discours convertit ? Tunnel par angle de mail (se remplit au fil des envois).
  const angles = statsParAngle(leads);

  // Boucle d'apprentissage : par cible, l'angle qui convertit le mieux → l'agent
  // PROPOSE de le privilégier (validé au moment de générer le brouillon sur la fiche).
  const recos = angleGagnantParCible(leads);
  // Mesure de la valeur : l'angle appris fait-il vraiment mieux ? (taux aligné vs autre)
  const lift = liftAngleAppris(leads);
  const { data: vData } = recos.length
    ? await supabase.from("verticales").select("id, nom")
    : { data: null };
  const cibleNom = new Map(
    ((vData as { id: string; nom: string }[] | null) ?? []).map((v) => [v.id, v.nom]),
  );

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">Suivi</h1>
      <p className="mb-5 text-sm text-[var(--muted)]">
        Pipeline d&apos;envoi et de réponses.
      </p>

      <ActionsBand source="suivi" actions={rankedActions} />

      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-8">
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
        <Stat label="RDV pris" value={rdvPris} />
        <Stat
          label="Taux de conversion"
          value={contactes ? `${Math.round((rdvPris / contactes) * 100)}%` : "—"}
        />
        <Stat
          label="Gagnés / Perdus"
          value={gagnes || perdus ? `${gagnes} 🏆 / ${perdus}` : "—"}
        />
        <Stat
          label="Rebonds"
          value={sent ? `${bounced} (${Math.round((bounced / sent) * 100)}%)` : bounced}
        />
      </div>

      {recos.length > 0 && (
        <div className="mb-6 rounded-2xl border border-[var(--brand)]/30 bg-gradient-to-br from-[var(--brand)]/5 to-transparent p-4">
          <h2 className="mb-1 text-sm font-semibold">
            💡 Angle recommandé par cible
          </h2>
          <p className="mb-3 text-xs text-[var(--muted)]">
            Ce qui convertit le mieux sur le terrain — l&apos;agent propose, tu valides
            en générant le brouillon. La reco s&apos;affine à chaque envoi.
          </p>
          {lift && (
            <div className="mb-3 rounded-xl border border-[var(--border)] bg-white px-3 py-2 text-sm">
              <span className="font-semibold">
                📈 Lift de l&apos;angle appris :{" "}
                <span className={lift.lift >= 0 ? "text-emerald-600" : "text-red-600"}>
                  {lift.lift >= 0 ? "+" : ""}
                  {lift.lift} pts
                </span>
              </span>
              <span className="ml-1 text-xs text-[var(--muted)]">
                — {lift.aligne.taux}% de réponse quand l&apos;angle envoyé suit la reco
                ({lift.aligne.envoyes} envois) vs {lift.autre.taux}% sinon (
                {lift.autre.envoyes}). La preuve que la boucle paie.
              </span>
            </div>
          )}
          <ul className="space-y-2 text-sm">
            {recos.map((r) => (
              <li
                key={r.verticaleId}
                className="flex flex-wrap items-baseline gap-x-2 gap-y-1 rounded-xl border border-[var(--border)] bg-white px-3 py-2"
              >
                <span className="font-medium">
                  {cibleNom.get(r.verticaleId) ?? "Cible"}
                </span>
                <span className="text-[var(--muted)]">→ privilégie</span>
                <span className="font-semibold">{ANGLE_LABEL[r.angle]}</span>
                <span className="text-xs text-[var(--muted)]">
                  {r.tauxReponse}% de réponse sur {r.envoyes} envois
                  {r.gagnes > 0 ? ` · ${r.gagnes} 🏆` : ""}
                  {r.avance != null && r.avance > 0
                    ? ` · +${r.avance} pts vs 2ᵉ angle`
                    : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {angles.length > 0 && (
        <div className="mb-6 rounded-2xl border border-[var(--border)] bg-white p-4">
          <h2 className="mb-1 text-sm font-semibold">📊 Quel discours convertit ?</h2>
          <p className="mb-3 text-xs text-[var(--muted)]">
            Tunnel par angle du mail (l&apos;angle est mémorisé à la génération du
            brouillon) — la boucle d&apos;apprentissage du ciblage.
          </p>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-[var(--muted)]">
                <th className="py-1.5 font-medium">Angle</th>
                <th className="py-1.5 font-medium">Envoyés</th>
                <th className="py-1.5 font-medium">Réponses</th>
                <th className="py-1.5 font-medium">Gagnés</th>
              </tr>
            </thead>
            <tbody>
              {angles.map((a) => (
                <tr key={a.angle} className="border-t border-[var(--border)]">
                  <td className="py-1.5 font-medium">
                    {a.angle === "sans_angle"
                      ? "Sans angle (anciens envois)"
                      : ANGLE_LABEL[a.angle]}
                  </td>
                  <td className="py-1.5">{a.envoyes}</td>
                  <td className="py-1.5">
                    {a.repondus}
                    {a.tauxReponse != null && (
                      <span className="ml-1 text-xs text-[var(--muted)]">({a.tauxReponse}%)</span>
                    )}
                  </td>
                  <td className="py-1.5">{a.gagnes > 0 ? `${a.gagnes} 🏆` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-7">
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
