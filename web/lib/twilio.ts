import type { SupabaseClient } from "@supabase/supabase-js";

// Cold-call inversé (modèle GetYourCall).
// Principe : on dépose un message vocal sur le répondeur du prospect depuis un
// numéro dédié (Twilio). Le prospect rappelle ce numéro ; l'appel entrant est
// routé vers nous et trace un « rappel reçu » sur le lead.
//
// ⚠️ STUB : la téléphonie réelle n'est pas branchée. Ce module pose le contrat
// et l'état de configuration ; le dépôt vocal effectif (Twilio Programmable
// Voice + détection répondeur/AMD) est un TODO. Aucune dépendance Twilio ici
// pour ne pas alourdir le build tant que ce n'est pas activé.

/** Vrai si les variables d'environnement Twilio sont présentes côté serveur. */
export function twilioConfigure(): boolean {
  return Boolean(
    process.env.TWILIO_ACCOUNT_SID &&
      process.env.TWILIO_AUTH_TOKEN &&
      process.env.TWILIO_FROM_NUMBER,
  );
}

type DepotResult =
  | { error: string; configured: boolean }
  | { ok: true; twilioSid: string };

/**
 * Dépose un message vocal sur le numéro du prospect.
 * STUB : renvoie une erreur explicite tant que Twilio n'est pas branché.
 */
export async function deposerMessageVocal(
  _supabase: SupabaseClient,
  _params: { leadId: string; toNumber: string; script?: string; audioUrl?: string },
): Promise<DepotResult> {
  if (!twilioConfigure())
    return {
      error: "Téléphonie non configurée (TWILIO_ACCOUNT_SID / AUTH_TOKEN / FROM_NUMBER).",
      configured: false,
    };
  // TODO(twilio): créer l'appel sortant, détecter le répondeur (AMD), jouer le
  // message (TwiML <Play>/<Say>), récupérer le CallSid, puis marquer 'depose'.
  return {
    error: "Dépôt vocal Twilio pas encore implémenté (structure en place).",
    configured: true,
  };
}
