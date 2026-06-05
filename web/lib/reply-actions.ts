// Incrément C — transitions de statut déduites de la classification d'une réponse.
// Mapping pur (sans accès serveur), partagé entre la route reply-draft (auto)
// et le composant reply-assistant (proposition 1 clic). Politique conservatrice :
// seule la transition « plus tard » est marquée `auto` (réversible, interne) ;
// les écartements restent proposés à la validation humaine.
import type { LeadStatus, ReplyCategorie } from "@/lib/database.types";

export type ReplyTransition = {
  statut: LeadStatus;
  label: string;
  // Appliquée automatiquement si reponse_statut_auto est activé.
  auto: boolean;
  // Pour les relances : nombre de jours avant la date de relance.
  relanceDansJours?: number;
};

export function transitionForCategorie(cat: ReplyCategorie): ReplyTransition | null {
  switch (cat) {
    case "plus_tard":
      return {
        statut: "a_relancer",
        label: "Planifier une relance (+3 sem.)",
        auto: true,
        relanceDansJours: 21,
      };
    case "pas_interesse":
      return { statut: "ecarte", label: "Écarter (pas intéressé)", auto: false };
    case "absence":
      return { statut: "ecarte", label: "Écarter (absence / auto-reply)", auto: false };
    case "mauvais_interlocuteur":
      return { statut: "ecarte", label: "Écarter (mauvais interlocuteur)", auto: false };
    // interesse / info / autre : pas de transition de statut (l'action utile est
    // l'envoi du brouillon, voire la prise de RDV captée par ailleurs).
    default:
      return null;
  }
}
