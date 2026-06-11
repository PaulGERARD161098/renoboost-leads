import Link from "next/link";
import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import type { Lead, LeadEvent, LeadMessage, Voicemail } from "@/lib/database.types";
import { LeadEditor } from "@/components/lead-editor";
import { LeadStatusActions } from "@/components/lead-status-actions";
import { LeadNotes } from "@/components/lead-notes";
import { LeadRelance } from "@/components/lead-relance";
import { SatellitePanel } from "@/components/satellite-panel";
import { MailThread } from "@/components/mail-thread";
import { ReplyAssistant } from "@/components/reply-assistant";
import { ColdCallPanel } from "@/components/cold-call-panel";
import { BornesLinks } from "@/components/bornes-links";
import { SignauxVeLies } from "@/components/signaux-ve-lies";
import { ContactCard } from "@/components/contact-card";
import { bornesProximite } from "@/lib/bornes";
import { signauxDuLead } from "@/lib/veille-signaux";
import { twilioConfigure } from "@/lib/twilio";
import {
  LEAD_STATUS_COLOR,
  LEAD_STATUS_LABEL,
  formatDate,
  nextAction,
  satelliteScore100,
  scoreColor,
  scoreGlobal,
  scoreVerdict,
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
  rebond: "Rebond (bounce)",
  oubli_rgpd: "Données effacées (RGPD)",
  message_vocal_depose: "Message vocal déposé",
  rappel_recu: "Rappel reçu",
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

  const { data: messages } = await supabase
    .from("lead_messages")
    .select("*")
    .eq("lead_id", id)
    .order("at", { ascending: true });

  const { data: voicemails } = await supabase
    .from("voicemails")
    .select("*")
    .eq("lead_id", id)
    .order("created_at", { ascending: false });

  // Proximité IRVE (bornes publiques) si le lead est géolocalisé.
  let irveProx: {
    rayon: number;
    rayonKm: number;
    surSite: number;
    plusProcheKm: number | null;
  } | null = null;
  if (l.latitude != null && l.longitude != null) {
    const p = await bornesProximite(supabase, l.latitude, l.longitude, 10);
    irveProx = {
      rayon: p.rayon,
      rayonKm: p.rayon_km,
      surSite: p.sur_site,
      plusProcheKm: p.plus_proche_km,
    };
  }


  // Signaux de veille rattachés à ce lead (interconnexion veille → lead).
  const signauxVeille = await signauxDuLead(supabase, l.id);

  const verdict = scoreVerdict(l.score);
  const action = nextAction(l);
  const satScore = satelliteScore100(l.vision_satellite);

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
        <div className="shrink-0 text-right">
          <span
            className={`inline-block rounded-full px-3 py-1 text-sm font-medium ${LEAD_STATUS_COLOR[l.statut]}`}
          >
            {LEAD_STATUS_LABEL[l.statut]}
          </span>
          {(l.statut === "gagne" || l.statut === "perdu") && l.issue_raison && (
            <p className="mt-1 max-w-[18rem] text-xs italic text-[var(--muted)]">
              {l.issue_raison}
            </p>
          )}
        </div>
      </div>

      {/* Bloc score "hero" */}
      <div className="mb-5 grid gap-4 rounded-2xl border border-[var(--border)] bg-white p-5 md:grid-cols-[auto_1fr]">
        <div className="flex items-center gap-4 md:pr-6 md:border-r md:border-[var(--border)]">
          <div
            className={`flex h-20 w-20 shrink-0 flex-col items-center justify-center rounded-2xl text-2xl font-extrabold ${scoreColor(l.score)}`}
          >
            {l.score ?? "—"}
            <span className="text-[10px] font-medium opacity-70">/ 100</span>
          </div>
          <div>
            <div className="text-xs uppercase tracking-wide text-[var(--muted)]">
              Score d&apos;intérêt
            </div>
            <span
              className={`mt-1 inline-block rounded-md px-2 py-0.5 text-sm font-semibold ${verdict.tone}`}
            >
              {verdict.label}
            </span>
            <ScoreBar score={l.score} />
            {satScore !== null && (
              <div className="mt-1.5 text-xs text-[var(--muted)]">
                Score global{" "}
                <span className="font-semibold text-[var(--text)]">
                  {scoreGlobal(l)}
                </span>{" "}
                · commercial {l.score ?? "—"} · ☀️ foncier {satScore}
              </div>
            )}
          </div>
        </div>
        <div className="flex flex-col justify-center">
          <div className="text-xs uppercase tracking-wide text-[var(--muted)]">
            Prochaine action recommandée
          </div>
          <p className="mt-1 text-sm font-medium">{action}</p>
          <LeadStatusActions lead={l} />
          <LeadRelance leadId={l.id} relanceAt={l.relance_at} />
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          {/* Pourquoi ce score */}
          <div className="rounded-xl border border-[var(--border)] bg-white p-5">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
              Pourquoi ce score
            </h2>
            {l.score_raison ? (
              <p className="text-sm leading-relaxed">{l.score_raison}</p>
            ) : (
              <p className="text-sm text-[var(--muted)]">
                Justification non disponible pour ce lead (créé avant l&apos;activation
                de l&apos;explicabilité). Les prochaines recherches l&apos;incluront.
              </p>
            )}
            {l.hors_filtre && l.raison_hors_filtre && (
              <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
                ⚠️ Hors cible : {l.raison_hors_filtre}
              </p>
            )}
          </div>

          <SatellitePanel
            leadId={l.id}
            initial={(l.vision_satellite as Record<string, unknown> | null) ?? null}
            canAnalyse={Boolean(
              (l.latitude != null && l.longitude != null) || l.adresse || l.ville,
            )}
            lat={l.latitude as number | null}
            lon={l.longitude as number | null}
          />

          <BornesLinks
            adresse={l.adresse}
            ville={l.ville}
            codePostal={l.code_postal}
            irve={irveProx}
          />

          <SignauxVeLies signaux={signauxVeille} />

          <MailThread messages={(messages as LeadMessage[] | null) ?? []} />

          {((messages as LeadMessage[] | null) ?? []).some(
            (m) => m.direction === "in",
          ) && <ReplyAssistant leadId={l.id} />}

          <ColdCallPanel
            leadId={l.id}
            initial={(voicemails as Voicemail[] | null) ?? []}
            configured={twilioConfigure()}
            hasPhone={Boolean(l.contact_tel)}
          />

          <LeadEditor lead={l} />
        </div>

        <div className="space-y-5">
          <div className="rounded-xl border border-[var(--border)] bg-white p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
              Entreprise
            </h2>
            <dl className="space-y-2 text-sm">
              <Field label="Secteur" value={l.libelle_naf ?? l.naf} />
              <Field label="Effectif" value={l.effectif} />
              <Field label="Ville" value={l.ville} />
              <Field label="SIREN" value={l.siren} />
            </dl>
          </div>

          <ContactCard
            leadId={l.id}
            initial={{
              contact_nom: l.contact_nom,
              contact_email: l.contact_email,
              contact_tel: l.contact_tel,
              contact_linkedin: l.contact_linkedin,
              entreprise_linkedin: l.entreprise_linkedin,
              site_web: l.site_web,
            }}
          />

          <div className="rounded-xl border border-[var(--border)] bg-white p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
              Historique & notes
            </h2>
            <LeadNotes leadId={l.id} />
            <ul className="space-y-3 text-sm">
              {(events as LeadEvent[] | null)?.length ? (
                (events as LeadEvent[]).map((ev) => {
                  const note =
                    ev.type === "note" &&
                    typeof ev.payload?.texte === "string"
                      ? (ev.payload.texte as string)
                      : null;
                  return (
                    <li key={ev.id}>
                      <div className="flex justify-between gap-2">
                        <span>{EVENT_LABEL[ev.type] ?? ev.type}</span>
                        <span className="text-xs text-[var(--muted)]">
                          {formatDate(ev.at)}
                        </span>
                      </div>
                      {note && (
                        <p className="mt-1 rounded-lg bg-slate-50 px-3 py-2 text-[var(--muted)]">
                          {note}
                        </p>
                      )}
                    </li>
                  );
                })
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

function ScoreBar({ score }: { score: number | null }) {
  const pct = Math.max(0, Math.min(100, score ?? 0));
  const color =
    score === null
      ? "bg-slate-300"
      : score >= 75
        ? "bg-emerald-500"
        : score >= 50
          ? "bg-amber-500"
          : "bg-slate-400";
  return (
    <div className="mt-2 h-1.5 w-40 max-w-full overflow-hidden rounded-full bg-slate-100">
      <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
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
