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
