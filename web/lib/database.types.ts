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
  | "rdv_pris"
  | "gagne"
  | "perdu"
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
  | "oubli_rgpd"
  | "message_vocal_depose"
  | "rappel_recu";

export interface Profile {
  id: string;
  email: string | null;
  nom: string | null;
  role: UserRole;
  last_seen_at: string | null;
  welcomed_v1_at: string | null;
  created_at: string;
}

export type RetourSource = "henry_popup" | "magellan";
export type RetourStatut = "nouveau" | "traite";

export interface Retour {
  id: string;
  source: RetourSource;
  page: string | null;
  texte: string;
  statut: RetourStatut;
  created_by: string | null;
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
  cout_detail: Record<string, number>;
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
  contact_linkedin: string | null;
  entreprise_linkedin: string | null;
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
  rdv_at: string | null;
  issue_raison: string | null;
  issue_at: string | null;
  mail_angle: "solaire" | "ombrieres" | "bornes" | null;
  campaign_id: string | null;
  call_statut: CallStatut | null;
  owner: string | null;
  created_at: string;
  updated_at: string;
}

export type BorneSource = "irve" | "rossini" | "chargemap";

export interface BorneRecharge {
  id: string;
  source: BorneSource;
  source_id: string | null;
  nom_station: string | null;
  operateur: string | null;
  amenageur: string | null;
  enseigne: string | null;
  lat: number | null;
  lng: number | null;
  puissance_kw: number | null;
  nb_points: number | null;
  adresse: string | null;
  code_postal: string | null;
  commune: string | null;
  departement: string | null;
  date_maj: string | null;
  raw: Record<string, unknown> | null;
  created_at: string;
}

export type CallStatut =
  | "a_appeler"
  | "message_depose"
  | "rappel_recu"
  | "injoignable";
export type VoicemailStatus =
  | "brouillon"
  | "planifie"
  | "depose"
  | "rappel_recu"
  | "echec";

export interface PhoneNumber {
  id: string;
  numero: string;
  label: string | null;
  provider: string;
  active: boolean;
  created_at: string;
}

export interface Voicemail {
  id: string;
  lead_id: string;
  campaign_id: string | null;
  from_number: string | null;
  to_number: string | null;
  script: string | null;
  audio_url: string | null;
  statut: VoicemailStatus;
  twilio_sid: string | null;
  deposed_at: string | null;
  callback_at: string | null;
  created_by: string | null;
  created_at: string;
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
  relance_auto: boolean;
  relance_delai_jours: number;
  relance_max: number;
  reponse_statut_auto: boolean;
  veille_auto_lead: boolean;
  veille_auto_seuil: number;
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

export type CampaignStatus = "brouillon" | "active" | "pausee" | "terminee";

export interface Campaign {
  id: string;
  nom: string;
  verticale_id: string | null;
  client_nom: string | null;
  statut: CampaignStatus;
  note: string | null;
  instantly_campaign_id: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export type MailDirection = "out" | "in";
export type MailSource = "manuel" | "instantly" | "systeme";

export interface LeadMessage {
  id: string;
  lead_id: string;
  direction: MailDirection;
  sujet: string | null;
  corps: string | null;
  from_email: string | null;
  to_email: string | null;
  source: MailSource;
  instantly_message_id: string | null;
  at: string;
}

export type Deadline = { label: string; date: string };

export interface AppContext {
  id: string;
  objectif_final: string | null;
  client_actif: string | null;
  deadlines: Deadline[];
  resume_session: string | null;
  resume_genere_le: string | null;
  calendly_url: string | null;
  telephone: string | null;
  updated_by: string | null;
  updated_at: string;
}

export interface WorkerHeartbeat {
  id: string;
  last_seen_at: string | null;
  mode: string | null;
  version: string | null;
  pending_runs: number;
  last_error: string | null;
  last_error_at: string | null;
  keys: Record<string, boolean>;
  updated_at: string;
}

export type SystemSeverite = "ok" | "warning" | "critical";

export interface SystemStatus {
  id: string;
  severite: SystemSeverite;
  message: string | null;
  since: string | null;
  updated_by: string | null;
  updated_at: string;
}

export type ReplyCategorie =
  | "interesse"
  | "info"
  | "plus_tard"
  | "mauvais_interlocuteur"
  | "pas_interesse"
  | "absence"
  | "autre";

export interface LeadReplySuggestion {
  id: string;
  lead_id: string;
  in_message_id: string | null;
  categorie: ReplyCategorie;
  confiance: number | null;
  sujet: string | null;
  brouillon: string;
  used: boolean;
  created_at: string;
}
