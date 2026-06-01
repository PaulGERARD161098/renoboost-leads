// Outils (lecture seule) de l'assistant — requêtes Supabase exposées à Claude.
// La RLS Supabase s'applique : le client est celui de l'utilisateur connecté.

import type { SupabaseClient } from "@supabase/supabase-js";
import { LEAD_STATUS_LABEL, RUN_STATUS_LABEL } from "../ui";
import type { Lead, LeadStatus, Run, Verticale } from "../database.types";

const STATUTS: LeadStatus[] = [
  "nouveau",
  "a_valider",
  "valide",
  "envoye",
  "ouvert",
  "repondu",
  "a_relancer",
  "ecarte",
];

export const tools = [
  {
    name: "compter_leads",
    description:
      "Statistiques globales : nombre total de leads, répartition par statut, score moyen, nombre d'envoyés/ouverts/répondus. Pour un état des lieux.",
    input_schema: { type: "object", properties: {} },
  },
  {
    name: "lister_leads",
    description:
      "Liste de leads filtrés et triés par score décroissant. Pour 'mes meilleurs leads', 'les leads à relancer dans telle ville', etc.",
    input_schema: {
      type: "object",
      properties: {
        statut: {
          type: "string",
          enum: STATUTS,
          description: "Filtre par statut (valeur technique).",
        },
        ville: { type: "string", description: "Filtre partiel sur la ville." },
        score_min: { type: "number", description: "Score minimum (0-100)." },
        top_only: {
          type: "boolean",
          description: "true = uniquement les top leads (score >= 75).",
        },
        limit: { type: "number", description: "Nombre max (défaut 15, max 50)." },
      },
    },
  },
  {
    name: "detail_lead",
    description:
      "Détail d'un lead recherché par nom d'entreprise (correspondance partielle).",
    input_schema: {
      type: "object",
      properties: {
        entreprise: { type: "string", description: "Nom (ou partie) de l'entreprise." },
      },
      required: ["entreprise"],
    },
  },
  {
    name: "lister_runs",
    description:
      "Recherches (runs) récentes avec statut, progression, nombre de leads collectés et coût. Pour 'où en est ma recherche'.",
    input_schema: {
      type: "object",
      properties: { limit: { type: "number", description: "Nombre max (défaut 5)." } },
    },
  },
  {
    name: "lister_cibles",
    description: "Cibles (verticales) actives définies dans le CRM.",
    input_schema: { type: "object", properties: {} },
  },
];

type Json = Record<string, unknown>;

function clampLimit(v: unknown, def: number, max: number): number {
  const n = typeof v === "number" && Number.isFinite(v) ? Math.floor(v) : def;
  return Math.min(Math.max(n, 1), max);
}

export async function executeTool(
  name: string,
  input: Json,
  supabase: SupabaseClient,
): Promise<string> {
  try {
    switch (name) {
      case "compter_leads": {
        const { data, error } = await supabase
          .from("leads")
          .select("statut, score")
          .limit(5000);
        if (error) return `Erreur: ${error.message}`;
        const leads = (data as Pick<Lead, "statut" | "score">[]) ?? [];
        const parStatut: Record<string, number> = {};
        let sommeScore = 0;
        let nbScore = 0;
        for (const l of leads) {
          const label = LEAD_STATUS_LABEL[l.statut] ?? l.statut;
          parStatut[label] = (parStatut[label] ?? 0) + 1;
          if (typeof l.score === "number") {
            sommeScore += l.score;
            nbScore++;
          }
        }
        const envoyes = leads.filter((l) =>
          ["envoye", "ouvert", "repondu"].includes(l.statut),
        ).length;
        const ouverts = leads.filter((l) =>
          ["ouvert", "repondu"].includes(l.statut),
        ).length;
        const repondus = leads.filter((l) => l.statut === "repondu").length;
        return JSON.stringify({
          total: leads.length,
          par_statut: parStatut,
          score_moyen: nbScore ? Math.round(sommeScore / nbScore) : null,
          envoyes,
          ouverts,
          repondus,
        });
      }

      case "lister_leads": {
        const limit = clampLimit(input.limit, 15, 50);
        let q = supabase
          .from("leads")
          .select(
            "entreprise, ville, code_postal, score, statut, contact_email, libelle_naf, effectif",
          )
          .order("score", { ascending: false, nullsFirst: false })
          .limit(limit);
        if (typeof input.statut === "string" && STATUTS.includes(input.statut as LeadStatus))
          q = q.eq("statut", input.statut);
        if (typeof input.ville === "string" && input.ville.trim())
          q = q.ilike("ville", `%${input.ville.trim()}%`);
        if (input.top_only === true) q = q.gte("score", 75);
        else if (typeof input.score_min === "number")
          q = q.gte("score", input.score_min);
        const { data, error } = await q;
        if (error) return `Erreur: ${error.message}`;
        const leads = (data as Partial<Lead>[]) ?? [];
        if (leads.length === 0) return "Aucun lead ne correspond à ces critères.";
        return JSON.stringify(
          leads.map((l) => ({
            entreprise: l.entreprise,
            ville: l.ville,
            score: l.score,
            statut: l.statut ? (LEAD_STATUS_LABEL[l.statut] ?? l.statut) : null,
            email: l.contact_email,
            activite: l.libelle_naf,
            effectif: l.effectif,
          })),
        );
      }

      case "detail_lead": {
        const nom = typeof input.entreprise === "string" ? input.entreprise.trim() : "";
        if (!nom) return "Précise un nom d'entreprise.";
        const { data, error } = await supabase
          .from("leads")
          .select("*")
          .ilike("entreprise", `%${nom}%`)
          .limit(3);
        if (error) return `Erreur: ${error.message}`;
        const leads = (data as Lead[]) ?? [];
        if (leads.length === 0) return `Aucun lead trouvé pour "${nom}".`;
        return JSON.stringify(
          leads.map((l) => ({
            entreprise: l.entreprise,
            ville: l.ville,
            code_postal: l.code_postal,
            siren: l.siren,
            activite: l.libelle_naf,
            effectif: l.effectif,
            score: l.score,
            statut: LEAD_STATUS_LABEL[l.statut] ?? l.statut,
            contact: l.contact_nom,
            email: l.contact_email,
            tel: l.contact_tel,
            site: l.site_web,
          })),
        );
      }

      case "lister_runs": {
        const limit = clampLimit(input.limit, 5, 20);
        const { data, error } = await supabase
          .from("runs")
          .select("status, progress, counts, cout_eur, etape_courante, zone, created_at")
          .order("created_at", { ascending: false })
          .limit(limit);
        if (error) return `Erreur: ${error.message}`;
        const runs = (data as Partial<Run>[]) ?? [];
        if (runs.length === 0)
          return "Aucune recherche lancée pour l'instant.";
        return JSON.stringify(
          runs.map((r) => ({
            statut: r.status ? (RUN_STATUS_LABEL[r.status] ?? r.status) : null,
            progression_pct: r.progress ?? 0,
            etape: r.etape_courante,
            leads: r.counts,
            cout_eur: r.cout_eur,
            zone: r.zone,
            date: r.created_at,
          })),
        );
      }

      case "lister_cibles": {
        const { data, error } = await supabase
          .from("verticales")
          .select("nom, slug, description, active")
          .eq("active", true)
          .order("nom");
        if (error) return `Erreur: ${error.message}`;
        const v = (data as Partial<Verticale>[]) ?? [];
        if (v.length === 0)
          return "Aucune cible active. En créer une dans l'onglet Cibles.";
        return JSON.stringify(
          v.map((c) => ({ nom: c.nom, slug: c.slug, description: c.description })),
        );
      }

      default:
        return `Outil inconnu : ${name}`;
    }
  } catch (e) {
    return `Erreur lors de l'exécution: ${e instanceof Error ? e.message : "inconnue"}`;
  }
}
