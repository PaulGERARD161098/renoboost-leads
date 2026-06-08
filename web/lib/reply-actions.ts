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
    case "interesse":
      // Prospect chaud → l'action terminale est le RDV. Proposée (jamais auto) :
      // on clique quand un créneau est calé, après la réponse.
      return { statut: "rdv_pris", label: "Marquer RDV pris", auto: false };
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
    // info / autre : pas de transition de statut (l'action utile est l'envoi
    // du brouillon de réponse).
    default:
      return null;
  }
}

/**
 * Prochaine action recommandée en clair, par catégorie de réponse — pour la ligne
 * « → Action recommandée » de l'assistant (pattern Contexte → Action → Données).
 * Couvre toutes les catégories, y compris celles sans transition de statut.
 */
export function actionRecommandeePourCategorie(cat: ReplyCategorie): string {
  switch (cat) {
    case "interesse":
      return "Réponds pour caler un créneau, puis marque le RDV pris.";
    case "info":
      return "Envoie la réponse avec l'info demandée — garde le fil chaud.";
    case "plus_tard":
      return "Planifie une relance dans ~3 semaines, pas d'insistance maintenant.";
    case "mauvais_interlocuteur":
      return "Demande le bon contact, puis écarte cette fiche.";
    case "pas_interesse":
      return "Accuse réception poliment et écarte la fiche.";
    case "absence":
      return "Absence / auto-reply : écarte ou attends le retour, ne relance pas.";
    default:
      return "Relis la réponse et choisis l'action adaptée.";
  }
}
