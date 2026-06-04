// Briefing d'accueil (« reprise au login », charte agent-first) : agrège ce qui
// est nouveau depuis la dernière session + calcule les priorités du jour, pour
// la modale d'accueil. Calculé côté serveur, consommé par <WelcomeModal>.
//
// Pattern Contexte → Actions → Données :
//   - « Quoi de neuf » = le contexte (où on en est, ce qui a bougé).
//   - « On fait quoi aujourd'hui » = les actions recommandées, cliquables.
import type { createClient } from "@/lib/supabase/server";
import type { Lead } from "@/lib/database.types";

export type Nouveaute = { icon: string; text: string; href: string };
export type Priorite = { label: string; hint: string; href: string; n: number };

export type Briefing = {
  shouldShow: boolean;
  prenom: string;
  dateLabel: string;
  objectif: string | null;
  resume: string | null;
  nouveautes: Nouveaute[];
  priorites: Priorite[];
};

// Clé de jour en heure de Paris (YYYY-MM-DD) : deux instants le « même jour »
// ne redéclenchent pas la modale. fr-CA rend un format ISO.
function dayKey(d: Date): string {
  return new Intl.DateTimeFormat("fr-CA", { timeZone: "Europe/Paris" }).format(d);
}

function prenomFrom(nom: string | null, email: string | null): string {
  const fromNom = nom?.trim().split(/\s+/)[0];
  if (fromNom) return fromNom;
  const local = email?.split("@")[0]?.split(/[.\-_]/)[0];
  if (local) return local.charAt(0).toUpperCase() + local.slice(1);
  return "à toi";
}

const A_TRAITER = ["nouveau", "a_valider", "valide"];

export async function getSessionBriefing(
  supabase: Awaited<ReturnType<typeof createClient>>,
  user: { id: string; email: string | null },
): Promise<Briefing> {
  const now = new Date();
  const dateLabel = now.toLocaleDateString("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  const { data: profile } = await supabase
    .from("profiles")
    .select("nom, last_seen_at")
    .eq("id", user.id)
    .maybeSingle();

  const prenom = prenomFrom(profile?.nom ?? null, user.email);
  const lastSeen: string | null = profile?.last_seen_at ?? null;
  const shouldShow = !lastSeen || dayKey(new Date(lastSeen)) !== dayKey(now);

  // Hors jour neuf : on évite les requêtes lourdes, la modale ne s'affichera pas.
  if (!shouldShow) {
    return {
      shouldShow: false,
      prenom,
      dateLabel,
      objectif: null,
      resume: null,
      nouveautes: [],
      priorites: [],
    };
  }

  // Référence pour « ce qui est nouveau » : la dernière session, ou 7 jours par
  // défaut à la toute première connexion.
  const sinceISO =
    lastSeen ?? new Date(now.getTime() - 7 * 86_400_000).toISOString();

  const [{ data: ctx }, { data: msgs }, { data: freshLeads }, { count: veilleNouveaux }] =
    await Promise.all([
      supabase
        .from("app_context")
        .select("objectif_final, resume_session")
        .eq("id", "main")
        .maybeSingle(),
      supabase
        .from("lead_messages")
        .select("id, sujet, at, lead:leads(id, entreprise)")
        .eq("direction", "in")
        .gt("at", sinceISO)
        .order("at", { ascending: false })
        .limit(5),
      supabase
        .from("leads")
        .select("id, created_at")
        .gt("created_at", sinceISO)
        .limit(1000),
      supabase
        .from("veille_signaux")
        .select("id", { count: "exact", head: true })
        .eq("statut", "nouveau")
        .gt("created_at", sinceISO),
    ]);

  // ---- « Quoi de neuf » : nouveautés depuis la dernière session.
  const nouveautes: Nouveaute[] = [];
  type MsgRow = {
    id: string;
    sujet: string | null;
    lead: { id: string; entreprise: string } | { id: string; entreprise: string }[] | null;
  };
  for (const m of (msgs as MsgRow[] | null) ?? []) {
    const lead = Array.isArray(m.lead) ? m.lead[0] : m.lead;
    if (!lead) continue;
    const sujet = m.sujet?.trim();
    nouveautes.push({
      icon: "✉️",
      text: `Réponse de ${lead.entreprise}${sujet ? ` — « ${sujet} »` : ""}`,
      href: `/leads/${lead.id}`,
    });
  }
  const nbLeads = (freshLeads as Pick<Lead, "id">[] | null)?.length ?? 0;
  if (nbLeads > 0) {
    nouveautes.push({
      icon: "🧲",
      text: `${nbLeads} nouveau${nbLeads > 1 ? "x" : ""} prospect${nbLeads > 1 ? "s" : ""} dans le pipeline`,
      href: "/inbox",
    });
  }
  if ((veilleNouveaux ?? 0) > 0) {
    nouveautes.push({
      icon: "🔔",
      text: `${veilleNouveaux} nouveau${(veilleNouveaux ?? 0) > 1 ? "x" : ""} signal${(veilleNouveaux ?? 0) > 1 ? "aux" : ""} de veille à examiner`,
      href: "/bornes",
    });
  }

  // ---- Priorités du jour : auto-calculées à partir des données live.
  const { data: leadsData } = await supabase
    .from("leads")
    .select("statut, score, relance_at, vision_satellite")
    .limit(5000);
  const leads = (leadsData as Partial<Lead>[]) ?? [];

  const endOfDay = new Date();
  endOfDay.setHours(23, 59, 59, 999);
  const relancesDues = leads.filter(
    (l) =>
      l.relance_at &&
      new Date(l.relance_at) <= endOfDay &&
      !["ecarte", "repondu"].includes(l.statut ?? ""),
  ).length;
  const aRepondu = leads.filter((l) => l.statut === "repondu").length;
  const aValider = leads.filter((l) => ["nouveau", "a_valider"].includes(l.statut ?? "")).length;
  const topNonContactes = leads.filter(
    (l) => (l.score ?? 0) >= 75 && A_TRAITER.includes(l.statut ?? ""),
  ).length;

  // Ordre = importance décroissante ; on ne garde que ce qui a du volume, max 5.
  const priorites: Priorite[] = [
    {
      label: "Traiter les réponses reçues",
      hint: "Un prospect a répondu — enchaîne le suivi commercial.",
      href: "/inbox?statut=repondu",
      n: aRepondu,
    },
    {
      label: "Faire les relances dues",
      hint: "Relances qui tombent aujourd'hui ou en retard.",
      href: "/suivi",
      n: relancesDues,
    },
    {
      label: "Examiner les signaux de veille",
      hint: "Intentions détectées à convertir en leads.",
      href: "/bornes",
      n: veilleNouveaux ?? 0,
    },
    {
      label: "Envoyer aux top leads",
      hint: "Leads à fort score jamais contactés — à prioriser.",
      href: "/inbox?statut=valide",
      n: topNonContactes,
    },
    {
      label: "Valider les nouveaux prospects",
      hint: "Leads en attente de validation avant envoi.",
      href: "/inbox",
      n: aValider,
    },
  ]
    .filter((p) => p.n > 0)
    .slice(0, 5);

  return {
    shouldShow: true,
    prenom,
    dateLabel,
    objectif: ctx?.objectif_final ?? null,
    resume: ctx?.resume_session ?? null,
    nouveautes,
    priorites,
  };
}
