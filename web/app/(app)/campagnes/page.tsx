import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import type { Campaign, CampaignStatus, Lead, Verticale } from "@/lib/database.types";
import { CampaignActions, CreateCampaignForm } from "@/components/campaigns-ui";
import { ActionsBand } from "@/components/actions-band";

export const dynamic = "force-dynamic";

const STATUT_LABEL: Record<CampaignStatus, string> = {
  brouillon: "Brouillon",
  active: "Active",
  pausee: "En pause",
  terminee: "Terminée",
};
const STATUT_COLOR: Record<CampaignStatus, string> = {
  brouillon: "bg-slate-100 text-slate-700",
  active: "bg-green-100 text-green-800",
  pausee: "bg-amber-100 text-amber-800",
  terminee: "bg-slate-200 text-slate-500",
};

type Funnel = {
  total: number;
  a_envoyer: number;
  envoyes: number;
  ouverts: number;
  repondus: number;
  rebonds: number;
};

function funnelDe(leads: Pick<Lead, "statut" | "sent_at" | "opened_at" | "replied_at" | "bounced_at">[]): Funnel {
  const f: Funnel = { total: leads.length, a_envoyer: 0, envoyes: 0, ouverts: 0, repondus: 0, rebonds: 0 };
  for (const l of leads) {
    if (l.statut === "valide") f.a_envoyer += 1;
    if (l.sent_at || ["envoye", "ouvert", "repondu"].includes(l.statut)) f.envoyes += 1;
    if (l.opened_at || ["ouvert", "repondu"].includes(l.statut)) f.ouverts += 1;
    if (l.replied_at || l.statut === "repondu") f.repondus += 1;
    if (l.bounced_at) f.rebonds += 1;
  }
  return f;
}

export default async function CampagnesPage({
  searchParams,
}: {
  searchParams: Promise<{ statut?: string; verticale?: string }>;
}) {
  const { statut: fStatut, verticale: fVerticale } = await searchParams;
  const supabase = await createClient();

  const [{ data: campaigns }, { data: verticales }, { data: leads }] = await Promise.all([
    supabase.from("campaigns").select("*").order("created_at", { ascending: false }),
    supabase.from("verticales").select("id, nom").eq("active", true).order("nom"),
    supabase
      .from("leads")
      .select("campaign_id, statut, sent_at, opened_at, replied_at, bounced_at")
      .not("campaign_id", "is", null),
  ]);

  const vListe = (verticales as Pick<Verticale, "id" | "nom">[] | null) ?? [];
  const vNom = new Map(vListe.map((v) => [v.id, v.nom]));

  // Entonnoir par campagne.
  const parCampagne = new Map<string, Funnel>();
  for (const c of (campaigns as Campaign[] | null) ?? []) {
    const siens = ((leads as Lead[] | null) ?? []).filter((l) => l.campaign_id === c.id);
    parCampagne.set(c.id, funnelDe(siens));
  }

  // Filtrage (vue affinée).
  let liste = ((campaigns as Campaign[] | null) ?? []).filter((c) => {
    if (fStatut && c.statut !== fStatut) return false;
    if (fVerticale && c.verticale_id !== fVerticale) return false;
    return true;
  });

  const qs = (patch: Record<string, string | undefined>) => {
    const p = new URLSearchParams();
    const s = patch.statut ?? fStatut;
    const v = patch.verticale ?? fVerticale;
    if (s) p.set("statut", s);
    if (v) p.set("verticale", v);
    const str = p.toString();
    return str ? `/campagnes?${str}` : "/campagnes";
  };

  const statuts: CampaignStatus[] = ["brouillon", "active", "pausee", "terminee"];

  // Contexte → Actions (pattern agent-first) : prochaines actions côté campagnes.
  const leadsCampagne = (leads as Pick<Lead, "statut">[] | null) ?? [];
  const campagnesActions = [
    {
      label: "Réponses à traiter",
      href: "/inbox?statut=repondu",
      n: leadsCampagne.filter((l) => l.statut === "repondu").length,
      hint: "Réponses reçues sur les campagnes — enchaîne le suivi.",
    },
    {
      label: "Prêts à envoyer",
      href: "/inbox?statut=valide",
      n: leadsCampagne.filter((l) => l.statut === "valide").length,
      hint: "Leads validés, prêts pour l'envoi.",
    },
    {
      label: "Campagnes en brouillon",
      href: "/campagnes?statut=brouillon",
      n: ((campaigns as Campaign[] | null) ?? []).filter((c) => c.statut === "brouillon").length,
      hint: "Campagnes à finaliser et activer.",
    },
  ];

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">Campagnes</h1>
      <p className="mb-5 text-sm text-[var(--muted)]">
        Pilotage global des campagnes d’emailing : lancement, pause, entonnoir et filtrage.
      </p>

      <ActionsBand source="campagnes" actions={campagnesActions} />

      <div className="mb-5">
        <CreateCampaignForm verticales={vListe} />
      </div>

      {/* Filtres */}
      <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-[var(--muted)]">Statut :</span>
        <Link
          href={qs({ statut: undefined })}
          className={`rounded-full px-3 py-1 ${!fStatut ? "bg-[var(--brand)] text-white" : "bg-slate-100 text-[var(--muted)]"}`}
        >
          Tous
        </Link>
        {statuts.map((s) => (
          <Link
            key={s}
            href={qs({ statut: fStatut === s ? undefined : s })}
            className={`rounded-full px-3 py-1 ${fStatut === s ? "bg-[var(--brand)] text-white" : "bg-slate-100 text-[var(--muted)]"}`}
          >
            {STATUT_LABEL[s]}
          </Link>
        ))}
        {vListe.length > 0 && (
          <>
            <span className="ml-3 text-[var(--muted)]">Verticale :</span>
            <Link
              href={qs({ verticale: undefined })}
              className={`rounded-full px-3 py-1 ${!fVerticale ? "bg-[var(--brand)] text-white" : "bg-slate-100 text-[var(--muted)]"}`}
            >
              Toutes
            </Link>
            {vListe.map((v) => (
              <Link
                key={v.id}
                href={qs({ verticale: fVerticale === v.id ? undefined : v.id })}
                className={`rounded-full px-3 py-1 ${fVerticale === v.id ? "bg-[var(--brand)] text-white" : "bg-slate-100 text-[var(--muted)]"}`}
              >
                {v.nom}
              </Link>
            ))}
          </>
        )}
      </div>

      {/* Liste */}
      {liste.length === 0 ? (
        <p className="rounded-xl border border-dashed border-[var(--border)] bg-white p-8 text-center text-sm text-[var(--muted)]">
          Aucune campagne {fStatut || fVerticale ? "pour ce filtre" : "pour l’instant"}. Crée-en une
          ci-dessus, puis rattache des leads depuis la liste des prospects.
        </p>
      ) : (
        <ul className="space-y-3">
          {liste.map((c) => {
            const f = parCampagne.get(c.id)!;
            return (
              <li
                key={c.id}
                className="rounded-xl border border-[var(--border)] bg-white p-5"
              >
                <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="font-semibold">{c.nom}</h2>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUT_COLOR[c.statut]}`}
                      >
                        {STATUT_LABEL[c.statut]}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--muted)]">
                      {c.verticale_id ? vNom.get(c.verticale_id) ?? "—" : "Toutes verticales"}
                      {" · "}
                      {f.total} lead{f.total > 1 ? "s" : ""}
                    </p>
                  </div>
                  <CampaignActions id={c.id} statut={c.statut} nbAEnvoyer={f.a_envoyer} />
                </div>

                {/* Entonnoir */}
                <div className="grid grid-cols-5 gap-2 text-center">
                  {[
                    ["À envoyer", f.a_envoyer],
                    ["Envoyés", f.envoyes],
                    ["Ouverts", f.ouverts],
                    ["Répondus", f.repondus],
                    ["Rebonds", f.rebonds],
                  ].map(([label, val]) => (
                    <div key={label as string} className="rounded-lg bg-slate-50 px-2 py-2">
                      <div className="text-lg font-bold">{val as number}</div>
                      <div className="text-xs text-[var(--muted)]">{label as string}</div>
                    </div>
                  ))}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
