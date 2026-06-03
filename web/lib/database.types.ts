// Types du schéma Supabase (maintenus à la main, miroir des migrations).
// Régénérables via : supabase gen types typescript --project-id gkvpvuipxyafvbwnqbab

export type UserRole = "admin" | "commercial";
export type RunStatus = "demande" | "en_cours" | "termine" | "echoue";
export type LeadStatus =
  | "nouveau"
  | "a_valider"
  | "valide"
  | "envoye"
  | "ouvert"
  | "repondu"
  | "a_relancer"
  | "ecarte";
export type LeadEventType =
  | "cree"
  | "envoye"
  | "ouvert"
  | "repondu"
  | "relance"
  | "ecarte"
  | "note"
  | "rebond"
  | "oubli_rgpd";

export interface Profile {
  id: string;
  email: string | null;
  nom: string | null;
  role: UserRole;
  created_at: string;
}

export interface Verticale {
  id: string;
  slug: string;
  nom: string;
  description: string | null;
  config: Record<string, unknown>;
  active: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export type RunQualite = "bonne" | "moyenne" | "mauvaise";

export interface Run {
  id: string;
  verticale_id: string | null;
  zone: Record<string, unknown>;
  volume_cible: number | null;
  budget_eur: number | null;
  status: RunStatus;
  etape_courante: string | null;
  progress: number;
  counts: Record<string, number>;
  cout_eur: number;
  log_url: string | null;
  erreur: string | null;
  is_test: boolean;
  nom: string | null;
  note: string | null;
  archive: boolean;
  qualite: RunQualite | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface Lead {
  id: string;
  run_id: string | null;
  verticale_id: string | null;
  entreprise: string;
  siren: string | null;
  siret: string | null;
  naf: string | null;
  libelle_naf: string | null;
  effectif: string | null;
  ville: string | null;
  code_postal: string | null;
  adresse: string | null;
  latitude: number | null;
  longitude: number | null;
  vision_satellite: Record<string, unknown> | null;
  score: number | null;
  score_raison: string | null;
  contact_nom: string | null;
  contact_email: string | null;
  contact_tel: string | null;
  site_web: string | null;
  hors_filtre: boolean;
  raison_hors_filtre: string | null;
  mail_sujet: string | null;
  mail_corps: string | null;
  statut: LeadStatus;
  instantly_id: string | null;
  sent_at: string | null;
  opened_at: string | null;
  replied_at: string | null;
  bounced_at: string | null;
  relance_at: string | null;
  owner: string | null;
  created_at: string;
  updated_at: string;
}

export interface ZoneCible {
  id: string;
  nom: string;
  adresse: string;
  rayon_km: number;
  created_by: string | null;
  created_at: string;
}

export interface VeilleSignal {
  id: string;
  entreprise: string;
  ville: string | null;
  type: string | null;
  declencheur: string | null;
  resume: string | null;
  source_url: string | null;
  source_date: string | null;
  score_intention: number | null;
  score_fit: number | null;
  angle: string | null;
  statut: string;
  lead_id: string | null;
  created_at: string;
}

export interface AgentConfig {
  id: string;
  autonomie: boolean;
  cibles_autorisees: string[];
  departements: string[];
  budget_jour_eur: number;
  budget_run_eur: number;
  volume_run: number;
  effectif_min: number | null;
  max_runs_jour: number;
  cadence_min: number;
  satellite_auto: boolean;
  updated_by: string | null;
  updated_at: string;
  created_at: string;
}

export interface AgentJournalEntry {
  id: string;
  at: string;
  type: string;
  message: string | null;
  run_id: string | null;
  cout_estime_eur: number | null;
  payload: Record<string, unknown>;
}

export interface LeadEvent {
  id: string;
  lead_id: string;
  type: LeadEventType;
  payload: Record<string, unknown>;
  actor: string | null;
  at: string;
}
