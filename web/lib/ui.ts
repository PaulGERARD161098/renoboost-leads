import type { LeadStatus, RunStatus } from "./database.types";

export const LEAD_STATUS_LABEL: Record<LeadStatus, string> = {
  nouveau: "Nouveau",
  a_valider: "À valider",
  valide: "Validé",
  envoye: "Envoyé",
  ouvert: "Ouvert",
  repondu: "Répondu",
  a_relancer: "À relancer",
  ecarte: "Écarté",
};

export const LEAD_STATUS_COLOR: Record<LeadStatus, string> = {
  nouveau: "bg-slate-100 text-slate-700",
  a_valider: "bg-amber-100 text-amber-800",
  valide: "bg-blue-100 text-blue-800",
  envoye: "bg-indigo-100 text-indigo-800",
  ouvert: "bg-violet-100 text-violet-800",
  repondu: "bg-emerald-100 text-emerald-800",
  a_relancer: "bg-orange-100 text-orange-800",
  ecarte: "bg-slate-200 text-slate-500",
};

export const RUN_STATUS_LABEL: Record<RunStatus, string> = {
  demande: "Demandé",
  en_cours: "En cours",
  termine: "Terminé",
  echoue: "Échoué",
};

export function scoreColor(score: number | null): string {
  if (score === null) return "bg-slate-100 text-slate-500";
  if (score >= 75) return "bg-emerald-100 text-emerald-800";
  if (score >= 50) return "bg-amber-100 text-amber-800";
  return "bg-slate-100 text-slate-600";
}

/** Verdict commercial associé à un score (label + classe de couleur). */
export function scoreVerdict(score: number | null): { label: string; tone: string } {
  if (score === null) return { label: "Non scoré", tone: "bg-slate-100 text-slate-500" };
  if (score >= 75)
    return { label: "Top lead — à prioriser", tone: "bg-emerald-100 text-emerald-800" };
  if (score >= 50) return { label: "Potentiel correct", tone: "bg-amber-100 text-amber-800" };
  return { label: "Faible intérêt", tone: "bg-slate-100 text-slate-600" };
}

/**
 * Score global = mélange du score commercial (intérêt) et du score foncier
 * (potentiel solaire satellite). Pondération 60/40 ; retombe sur l'un si l'autre
 * est absent.
 */
export function scoreGlobal(lead: {
  score?: number | null;
  vision_satellite?: Record<string, unknown> | null;
}): number | null {
  const com = typeof lead.score === "number" ? lead.score : null;
  const v = lead.vision_satellite as { score?: number } | null;
  const sat = typeof v?.score === "number" ? v.score : null;
  if (com === null && sat === null) return null;
  if (sat === null) return com;
  if (com === null) return sat;
  return Math.round(0.6 * com + 0.4 * sat);
}

/** Prochaine action recommandée selon le statut, le score et la présence d'email. */
export function nextAction(lead: {
  statut: LeadStatus;
  score: number | null;
  contact_email: string | null;
}): string {
  switch (lead.statut) {
    case "repondu":
      return "A répondu — enchaîne le suivi commercial (RDV, devis).";
    case "ouvert":
      return "A ouvert sans répondre — prévois une relance ciblée.";
    case "a_relancer":
      return "À relancer — renvoie un message court de relance.";
    case "envoye":
      return "Email envoyé — surveille l'ouverture.";
    case "ecarte":
      return "Écarté — aucune action.";
    case "valide":
      return lead.contact_email
        ? "Validé — prêt à envoyer."
        : "Validé mais email manquant — complète le contact.";
    default:
      if (!lead.contact_email) return "Vérifie/complète l'email avant tout envoi.";
      if ((lead.score ?? 0) >= 75)
        return "Top lead jamais contacté — valide l'email et envoie en priorité.";
      if ((lead.score ?? 0) >= 50) return "Potentiel correct — relis le pitch puis envoie.";
      return "Score faible — à qualifier ou écarter.";
  }
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
