import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import type { AppContext, Lead } from "@/lib/database.types";
import { HomeCommand } from "@/components/home-command";
import { HomeModes } from "@/components/home-modes";
import { WelcomeGreeting } from "@/components/welcome-greeting";
import { WorkerStatus } from "@/components/worker-status";
import { AppelsDuJour } from "@/components/appels-du-jour";
import { fileAppelsDuJour, type LeadAppel } from "@/lib/appels-du-jour";

// Poste de pilotage (charte agent-first) : l'arrivée n'est plus l'inbox brute mais
// une macro-page qui ORIENTE — synthèse Magellan en tête, 4 grands blocs d'entrée,
// et une commande vocale pour parler à l'agent. Pattern Contexte → Actions → Données.
export const dynamic = "force-dynamic";

const A_TRAITER = ["nouveau", "a_valider", "valide"];

function prenomFrom(nom: string | null, email: string | null): string {
  const fromNom = nom?.trim().split(/\s+/)[0];
  if (fromNom) return fromNom;
  const local = email?.split("@")[0]?.split(/[.\-_]/)[0];
  if (local) return local.charAt(0).toUpperCase() + local.slice(1);
  return "à toi";
}

export default async function AccueilPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // ── Contexte (où on en est) ──────────────────────────────────────────
  const [{ data: profile }, { data: ctxData }] = await Promise.all([
    supabase.from("profiles").select("nom").eq("id", user?.id ?? "").maybeSingle(),
    supabase.from("app_context").select("*").eq("id", "main").maybeSingle(),
  ]);
  const prenom = prenomFrom(profile?.nom ?? null, user?.email ?? null);
  const context = ctxData as AppContext | null;

  const dateLabel = new Date().toLocaleDateString("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  // ── Données live pour les compteurs des blocs ────────────────────────
  const endOfDay = new Date();
  endOfDay.setHours(23, 59, 59, 999);

  const [
    { count: campagnesActives },
    { data: leadsData },
    { count: veilleNouveaux },
  ] = await Promise.all([
    supabase
      .from("campaigns")
      .select("id", { count: "exact", head: true })
      .eq("statut", "active"),
    supabase.from("leads").select("statut, score, relance_at").limit(5000),
    supabase
      .from("veille_signaux")
      .select("id", { count: "exact", head: true })
      .eq("statut", "nouveau"),
  ]);

  const leads = (leadsData as Partial<Lead>[]) ?? [];
  const repondus = leads.filter((l) => l.statut === "repondu").length;
  const relancesDues = leads.filter(
    (l) =>
      l.relance_at &&
      new Date(l.relance_at) <= endOfDay &&
      !["ecarte", "repondu"].includes(l.statut ?? ""),
  ).length;
  const rdvPris = leads.filter((l) => l.statut === "rdv_pris").length;
  const aValider = leads.filter((l) =>
    ["nouveau", "a_valider"].includes(l.statut ?? ""),
  ).length;
  const topNonContactes = leads.filter(
    (l) => (l.score ?? 0) >= 75 && A_TRAITER.includes(l.statut ?? ""),
  ).length;

  const alertes = repondus + (veilleNouveaux ?? 0) + relancesDues;

  // ── File d'appels du jour : qui appeler ce matin, et pourquoi ────────
  const { data: appelsData } = await supabase
    .from("leads")
    .select(
      "id, entreprise, ville, statut, score, contact_nom, contact_tel, relance_at, call_statut, score_raison, vision_satellite",
    )
    .in("statut", ["repondu", "a_relancer", "envoye", "ouvert", "valide", "nouveau", "a_valider"])
    .order("score", { ascending: false, nullsFirst: false })
    .limit(400);
  const fileAppels = fileAppelsDuJour((appelsData as LeadAppel[] | null) ?? []);

  // ── Prochaine action prioritaire (la synthèse pointe vers UNE chose) ──
  const prochaines = [
    { label: "traiter les réponses reçues", n: repondus, href: "/inbox?statut=repondu" },
    { label: "faire les relances dues", n: relancesDues, href: "/suivi" },
    { label: "examiner les signaux de veille", n: veilleNouveaux ?? 0, href: "/bornes" },
    { label: "envoyer aux top leads", n: topNonContactes, href: "/inbox?statut=valide" },
    { label: "valider les nouveaux prospects", n: aValider, href: "/inbox" },
  ].filter((p) => p.n > 0);
  const prochaine = prochaines[0] ?? null;

  const blocs = [
    {
      key: "campagnes",
      icon: "✉️",
      titre: "Campagnes en cours",
      sous: "Suivre et piloter les envois en cours.",
      n: campagnesActives ?? 0,
      nLabel: (campagnesActives ?? 0) > 1 ? "actives" : "active",
      href: "/campagnes",
    },
    {
      key: "alertes",
      icon: "🔔",
      titre: "Alertes à traiter",
      sous: "Réponses, relances dues et signaux de veille.",
      n: alertes,
      nLabel: alertes > 1 ? "à traiter" : "à traiter",
      href: "/inbox?statut=repondu",
    },
    {
      key: "rdv",
      icon: "📅",
      titre: "Rendez-vous",
      sous: "Le calendrier de tes RDV clients.",
      n: rdvPris,
      nLabel: rdvPris > 1 ? "à venir" : "à venir",
      href: "/rendez-vous",
    },
  ];

  return (
    <div>
      {/* ── Bandeau synthèse Magellan (agent présent dès l'arrivée) ── */}
      <div className="mb-6 rounded-2xl border border-[var(--brand)]/30 bg-gradient-to-br from-[var(--brand)]/10 via-[var(--brand)]/5 to-transparent p-6">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 text-2xl">🧭</span>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium capitalize text-[var(--muted)]">
              {dateLabel}
            </p>
            <WelcomeGreeting prenom={prenom} />

            {context?.objectif_final && (
              <p className="mt-2 text-sm">
                <span className="text-[var(--muted)]">🎯 Objectif : </span>
                {context.objectif_final}
              </p>
            )}

            <p className="mt-2 text-sm leading-relaxed text-slate-700">
              {context?.resume_session ? (
                <>📝 {context.resume_session}</>
              ) : (
                <>Voilà où on en est : {leads.length} prospects au pipeline.</>
              )}
            </p>

            {prochaine ? (
              <Link
                href={prochaine.href}
                className="mt-3 inline-flex items-center gap-2 rounded-lg bg-[var(--brand)] px-3.5 py-2 text-sm font-medium text-white hover:bg-[var(--brand-dark)]"
              >
                ⚡ Prochaine action : {prochaine.label}
                <span className="rounded-full bg-white/25 px-2 py-0.5 text-xs font-semibold">
                  {prochaine.n}
                </span>
                <span>→</span>
              </Link>
            ) : (
              <p className="mt-3 text-sm text-[var(--muted)]">
                Rien d&apos;urgent — bon moment pour lancer une recherche.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* ── État du moteur : le worker traite-t-il les recherches ? ── */}
      <div className="mb-5">
        <WorkerStatus />
      </div>

      {/* ── La liste du matin : appels prioritaires (agent-first) ── */}
      <AppelsDuJour file={fileAppels} />

      {/* ── Accès rapides : mode déplacement (vocal) + visite guidée ── */}
      <HomeModes />

      {/* ── Commande vocale : parler à l'agent, orienter vite ── */}
      <HomeCommand />

      {/* ── 4 grands blocs sélectionnables (même style, bandeau au-dessus) ── */}
      <h2 className="mb-3 mt-7 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
        Où veux-tu aller ?
      </h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {blocs.map((b) => (
          <Link
            key={b.key}
            href={b.href}
            className="group flex flex-col overflow-hidden rounded-2xl border border-[var(--border)] bg-white transition hover:-translate-y-0.5 hover:border-[var(--brand)] hover:shadow-lg"
          >
            {/* Bandeau au-dessus */}
            <div className="flex items-center justify-between bg-[var(--brand)] px-4 py-2.5 text-white">
              <span className="text-lg">{b.icon}</span>
              <span className="rounded-full bg-white/20 px-2.5 py-0.5 text-xs font-bold">
                {b.n} {b.nLabel}
              </span>
            </div>
            <div className="flex flex-1 flex-col p-4">
              <div className="text-base font-semibold group-hover:text-[var(--brand)]">
                {b.titre}
              </div>
              <p className="mt-1 flex-1 text-sm text-[var(--muted)]">{b.sous}</p>
              <span className="mt-3 text-sm font-medium text-[var(--brand)]">
                Ouvrir →
              </span>
            </div>
          </Link>
        ))}

        {/* 4e bloc : Autre chose ? → ouvre Magellan en recherche libre */}
        <button
          data-magellan-open
          className="group flex flex-col overflow-hidden rounded-2xl border border-dashed border-[var(--brand)]/50 bg-[var(--brand)]/5 text-left transition hover:-translate-y-0.5 hover:border-[var(--brand)] hover:shadow-lg"
        >
          <div className="flex items-center justify-between bg-[var(--brand)] px-4 py-2.5 text-white">
            <span className="text-lg">💬</span>
            <span className="rounded-full bg-white/20 px-2.5 py-0.5 text-xs font-bold">
              Magellan
            </span>
          </div>
          <div className="flex flex-1 flex-col p-4">
            <div className="text-base font-semibold group-hover:text-[var(--brand)]">
              Autre chose ?
            </div>
            <p className="mt-1 flex-1 text-sm text-[var(--muted)]">
              Décris ta demande à l&apos;agent pour affiner la recherche.
            </p>
            <span className="mt-3 text-sm font-medium text-[var(--brand)]">
              Parler à Magellan →
            </span>
          </div>
        </button>
      </div>
    </div>
  );
}
