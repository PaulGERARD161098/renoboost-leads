// Outils (lecture seule) de l'assistant — requêtes Supabase exposées à Claude.
// La RLS Supabase s'applique : le client est celui de l'utilisateur connecté.

import type { SupabaseClient } from "@supabase/supabase-js";
import { LEAD_STATUS_LABEL, RUN_STATUS_LABEL } from "../ui";
import { analyseSatellite } from "../satellite";
import type {
  AgentConfig,
  AgentJournalEntry,
  Lead,
  LeadStatus,
  Run,
  Verticale,
} from "../database.types";

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
    name: "stats_recherches",
    description:
      "Performance comparée des recherches (runs) : par recherche, nombre de leads, score moyen, nombre de top leads, nombre de réponses, coût et département. Pour 'quelles ont été mes meilleures recherches'.",
    input_schema: {
      type: "object",
      properties: {
        limit: { type: "number", description: "Nombre de recherches à comparer (défaut 10)." },
      },
    },
  },
  {
    name: "stats_departements",
    description:
      "Performance agrégée par département (déduit du code postal des leads) : volume, score moyen, top leads, réponses, taux de réponse. Pour 'quels sont mes meilleurs départements'.",
    input_schema: { type: "object", properties: {} },
  },
  {
    name: "lister_cibles",
    description: "Cibles (verticales) actives définies dans le CRM.",
    input_schema: { type: "object", properties: {} },
  },
  {
    name: "lancer_recherche",
    description:
      "ACTION qui engage du budget : crée une nouvelle recherche (run). À n'appeler QU'APRÈS confirmation explicite de l'utilisateur sur les paramètres proposés. Le moteur exécute ensuite la recherche en tâche de fond.",
    input_schema: {
      type: "object",
      properties: {
        cible: {
          type: "string",
          description: "Nom ou slug de la cible (verticale) active.",
        },
        departement: {
          type: "string",
          description: "Numéro de département, ex: '59'. Utiliser SOIT départment SOIT adresse.",
        },
        adresse: {
          type: "string",
          description:
            "Adresse/zone centrale pour une recherche géolocalisée (ex: 'ZA de Wambrechies, 59118'). Le moteur géocode et cherche dans un rayon. Alternative au département.",
        },
        rayon_km: {
          type: "number",
          description: "Rayon de recherche en km autour de l'adresse (défaut 10).",
        },
        budget_eur: {
          type: "number",
          description: "Budget plafond en euros pour cette recherche.",
        },
        volume_cible: { type: "number", description: "Nombre de leads visé (optionnel)." },
        effectif_min: { type: "number", description: "Effectif minimum (optionnel)." },
      },
      required: ["cible", "budget_eur"],
    },
  },
  {
    name: "resultats_recherche",
    description:
      "Leads issus d'une recherche, triés par score, pour livrer un résultat propre. Par défaut la recherche la plus récente ; sinon préciser un département.",
    input_schema: {
      type: "object",
      properties: {
        departement: {
          type: "string",
          description: "Filtrer sur la recherche d'un département (optionnel).",
        },
        limit: { type: "number", description: "Nombre de leads (défaut 25, max 50)." },
      },
    },
  },
  {
    name: "statut_agent",
    description:
      "État du mandat de l'agent autonome : autonomie on/off, périmètre, budget/jour, budget engagé aujourd'hui, dernières actions automatiques. Pour 'qu'a fait l'agent', 'l'autonomie est-elle active'.",
    input_schema: { type: "object", properties: {} },
  },
  {
    name: "meilleures_zones",
    description:
      "Localités (villes) les plus performantes : volume, score moyen, top leads, réponses. Pour suggérer OÙ prospecter ensuite (quelle zone cibler).",
    input_schema: { type: "object", properties: {} },
  },
  {
    name: "lister_zones_cibles",
    description:
      "Zones cibles enregistrées (nom, adresse centrale, rayon km), réutilisables pour lancer une recherche géolocalisée.",
    input_schema: { type: "object", properties: {} },
  },
  {
    name: "analyser_satellite",
    description:
      "Analyse le potentiel solaire d'un lead (toiture + parking + ombrières) via sa vue aérienne IGN et l'IA vision. ACTION (consomme un appel IA). Donne le nom de l'entreprise.",
    input_schema: {
      type: "object",
      properties: {
        entreprise: { type: "string", description: "Nom (ou partie) de l'entreprise du lead." },
      },
      required: ["entreprise"],
    },
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
          .select("statut, score, bounced_at")
          .limit(5000);
        if (error) return `Erreur: ${error.message}`;
        const leads =
          (data as Pick<Lead, "statut" | "score" | "bounced_at">[]) ?? [];
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
        const bounces = leads.filter((l) => l.bounced_at).length;
        return JSON.stringify({
          total: leads.length,
          par_statut: parStatut,
          score_moyen: nbScore ? Math.round(sommeScore / nbScore) : null,
          envoyes,
          ouverts,
          repondus,
          bounces,
          taux_ouverture_pct: envoyes ? Math.round((ouverts / envoyes) * 100) : null,
          taux_reponse_pct: envoyes ? Math.round((repondus / envoyes) * 100) : null,
          taux_bounce_pct: envoyes ? Math.round((bounces / envoyes) * 100) : null,
        });
      }

      case "lister_leads": {
        const limit = clampLimit(input.limit, 15, 50);
        let q = supabase
          .from("leads")
          .select(
            "id, entreprise, ville, code_postal, score, statut, contact_email, libelle_naf, effectif",
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
            id: l.id,
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
            id: l.id,
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
            pitch_objet: l.mail_sujet,
            pitch_corps: l.mail_corps,
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

      case "stats_recherches": {
        const limit = clampLimit(input.limit, 10, 30);
        const { data: runsData, error: runsErr } = await supabase
          .from("runs")
          .select("id, zone, status, cout_eur, created_at")
          .order("created_at", { ascending: false })
          .limit(50);
        if (runsErr) return `Erreur: ${runsErr.message}`;
        const runs = (runsData as Partial<Run>[]) ?? [];
        if (runs.length === 0) return "Aucune recherche lancée pour l'instant.";

        const { data: leadsData, error: leadsErr } = await supabase
          .from("leads")
          .select("run_id, score, statut")
          .limit(5000);
        if (leadsErr) return `Erreur: ${leadsErr.message}`;
        const leads =
          (leadsData as Pick<Lead, "run_id" | "score" | "statut">[]) ?? [];

        type Agg = { n: number; somme: number; nbScore: number; top: number; repondus: number };
        const par: Record<string, Agg> = {};
        for (const l of leads) {
          if (!l.run_id) continue;
          const a = (par[l.run_id] ??= { n: 0, somme: 0, nbScore: 0, top: 0, repondus: 0 });
          a.n++;
          if (typeof l.score === "number") {
            a.somme += l.score;
            a.nbScore++;
            if (l.score >= 75) a.top++;
          }
          if (l.statut === "repondu") a.repondus++;
        }

        const rows = runs
          .map((r) => {
            const a = par[r.id as string] ?? { n: 0, somme: 0, nbScore: 0, top: 0, repondus: 0 };
            const zone = r.zone as { departement?: string } | undefined;
            return {
              departement: zone?.departement ?? null,
              date: r.created_at,
              statut: r.status ? (RUN_STATUS_LABEL[r.status] ?? r.status) : null,
              leads: a.n,
              score_moyen: a.nbScore ? Math.round(a.somme / a.nbScore) : null,
              top_leads: a.top,
              reponses: a.repondus,
              cout_eur: r.cout_eur ?? 0,
            };
          })
          .sort(
            (x, y) =>
              y.reponses - x.reponses ||
              y.top_leads - x.top_leads ||
              (y.score_moyen ?? 0) - (x.score_moyen ?? 0),
          )
          .slice(0, limit);
        return JSON.stringify(rows);
      }

      case "stats_departements": {
        const { data, error } = await supabase
          .from("leads")
          .select("code_postal, score, statut")
          .limit(5000);
        if (error) return `Erreur: ${error.message}`;
        const leads =
          (data as Pick<Lead, "code_postal" | "score" | "statut">[]) ?? [];
        if (leads.length === 0) return "Aucun lead pour l'instant.";

        type Agg = { n: number; somme: number; nbScore: number; top: number; envoyes: number; repondus: number };
        const par: Record<string, Agg> = {};
        for (const l of leads) {
          const dep = l.code_postal ? l.code_postal.slice(0, 2) : "??";
          const a = (par[dep] ??= { n: 0, somme: 0, nbScore: 0, top: 0, envoyes: 0, repondus: 0 });
          a.n++;
          if (typeof l.score === "number") {
            a.somme += l.score;
            a.nbScore++;
            if (l.score >= 75) a.top++;
          }
          if (["envoye", "ouvert", "repondu"].includes(l.statut)) a.envoyes++;
          if (l.statut === "repondu") a.repondus++;
        }

        const rows = Object.entries(par)
          .map(([dep, a]) => ({
            departement: dep,
            leads: a.n,
            score_moyen: a.nbScore ? Math.round(a.somme / a.nbScore) : null,
            top_leads: a.top,
            reponses: a.repondus,
            taux_reponse_pct: a.envoyes ? Math.round((a.repondus / a.envoyes) * 100) : null,
          }))
          .sort((x, y) => y.top_leads - x.top_leads || y.leads - x.leads);
        return JSON.stringify(rows);
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

      case "lancer_recherche": {
        const cible = typeof input.cible === "string" ? input.cible.trim() : "";
        const departement =
          typeof input.departement === "string" ? input.departement.trim() : "";
        const adresse =
          typeof input.adresse === "string" ? input.adresse.trim() : "";
        const rayonKm =
          typeof input.rayon_km === "number" ? input.rayon_km : 10;
        const budget = typeof input.budget_eur === "number" ? input.budget_eur : null;
        const volume = typeof input.volume_cible === "number" ? input.volume_cible : null;
        const effectifMin =
          typeof input.effectif_min === "number" ? input.effectif_min : null;
        if (!cible) return "Précise la cible (verticale).";
        if (!departement && !adresse)
          return "Précise une zone : un département (ex: 59) OU une adresse centrale.";
        if (budget === null || budget <= 0)
          return "Précise un budget plafond en euros (ex: 15).";

        const { data: vData, error: vErr } = await supabase
          .from("verticales")
          .select("id, slug, nom")
          .eq("active", true);
        if (vErr) return `Erreur: ${vErr.message}`;
        const verticales =
          (vData as Pick<Verticale, "id" | "slug" | "nom">[]) ?? [];
        const needle = cible.toLowerCase();
        const matches = verticales.filter(
          (v) =>
            v.slug.toLowerCase().includes(needle) ||
            v.nom.toLowerCase().includes(needle),
        );
        if (matches.length === 0)
          return `Cible introuvable. Cibles actives : ${verticales.map((v) => v.nom).join(", ") || "aucune"}.`;
        if (matches.length > 1)
          return `Plusieurs cibles correspondent : ${matches.map((v) => v.nom).join(", ")}. Précise laquelle.`;
        const verticale = matches[0];

        const zone: Record<string, unknown> = { effectif_min: effectifMin };
        if (adresse) {
          zone.adresse = adresse;
          zone.rayon_par_point_km = rayonKm;
        } else {
          zone.departement = departement;
        }

        const {
          data: { user },
        } = await supabase.auth.getUser();
        const { data, error } = await supabase
          .from("runs")
          .insert({
            verticale_id: verticale.id,
            zone,
            volume_cible: volume,
            budget_eur: budget,
            status: "demande",
            created_by: user?.id ?? null,
          })
          .select("id")
          .single();
        if (error) return `Erreur lors du lancement : ${error.message}`;
        return JSON.stringify({
          ok: true,
          run_id: data.id,
          cible: verticale.nom,
          zone: adresse ? `${adresse} (${rayonKm} km)` : `Dépt ${departement}`,
          budget_eur: budget,
          volume_cible: volume,
          message:
            "Recherche créée (statut : demandé). Le moteur va l'exécuter en tâche de fond ; les résultats arriveront dans l'onglet Prospects.",
        });
      }

      case "resultats_recherche": {
        const limit = clampLimit(input.limit, 25, 50);
        const dep =
          typeof input.departement === "string" ? input.departement.trim() : "";
        const { data: runsData, error: runsErr } = await supabase
          .from("runs")
          .select("id, zone, status, created_at, cout_eur")
          .order("created_at", { ascending: false })
          .limit(20);
        if (runsErr) return `Erreur: ${runsErr.message}`;
        const runs = (runsData as Partial<Run>[]) ?? [];
        if (runs.length === 0) return "Aucune recherche lancée pour l'instant.";
        let target = runs[0];
        if (dep) {
          const m = runs.find(
            (r) => (r.zone as { departement?: string } | undefined)?.departement === dep,
          );
          if (m) target = m;
        }
        const { data: leadsData, error } = await supabase
          .from("leads")
          .select("id, entreprise, ville, score, statut, contact_email, libelle_naf")
          .eq("run_id", target.id as string)
          .order("score", { ascending: false, nullsFirst: false })
          .limit(limit);
        if (error) return `Erreur: ${error.message}`;
        const leads = (leadsData as Partial<Lead>[]) ?? [];
        const meta = {
          statut_recherche: target.status
            ? (RUN_STATUS_LABEL[target.status] ?? target.status)
            : null,
          departement:
            (target.zone as { departement?: string } | undefined)?.departement ?? null,
          cout_eur: target.cout_eur,
          nb_resultats: leads.length,
        };
        if (leads.length === 0)
          return JSON.stringify({
            ...meta,
            message:
              "Pas encore de résultats — la recherche est probablement en cours.",
            leads: [],
          });
        return JSON.stringify({
          ...meta,
          leads: leads.map((l) => ({
            id: l.id,
            entreprise: l.entreprise,
            ville: l.ville,
            score: l.score,
            statut: l.statut ? (LEAD_STATUS_LABEL[l.statut] ?? l.statut) : null,
            email: l.contact_email,
            activite: l.libelle_naf,
          })),
        });
      }

      case "statut_agent": {
        const { data: cfgData } = await supabase
          .from("agent_config")
          .select("*")
          .order("created_at", { ascending: true })
          .limit(1)
          .maybeSingle();
        const cfg = cfgData as AgentConfig | null;
        if (!cfg) return "Agent non configuré.";

        const startOfDay = new Date();
        startOfDay.setHours(0, 0, 0, 0);
        const { data: runsToday } = await supabase
          .from("runs")
          .select("budget_eur")
          .gte("created_at", startOfDay.toISOString());
        const engage = ((runsToday as { budget_eur: number | null }[]) ?? []).reduce(
          (s, r) => s + Number(r.budget_eur ?? 0),
          0,
        );

        const { data: jData } = await supabase
          .from("agent_journal")
          .select("at, type, message")
          .order("at", { ascending: false })
          .limit(8);
        const journal = (jData as Partial<AgentJournalEntry>[]) ?? [];

        return JSON.stringify({
          autonomie: cfg.autonomie,
          departements: cfg.departements,
          cibles_autorisees_count: cfg.cibles_autorisees.length,
          budget_jour_eur: cfg.budget_jour_eur,
          budget_engage_aujourdhui_eur: Math.round(engage),
          budget_run_eur: cfg.budget_run_eur,
          max_runs_jour: cfg.max_runs_jour,
          cadence_min: cfg.cadence_min,
          dernieres_actions: journal.map((j) => ({
            quand: j.at,
            type: j.type,
            message: j.message,
          })),
        });
      }

      case "meilleures_zones": {
        const { data, error } = await supabase
          .from("leads")
          .select("ville, score, statut")
          .limit(5000);
        if (error) return `Erreur: ${error.message}`;
        const leads =
          (data as Pick<Lead, "ville" | "score" | "statut">[]) ?? [];
        type Agg = { n: number; somme: number; nbScore: number; top: number; rep: number };
        const par: Record<string, Agg> = {};
        for (const l of leads) {
          const v = (l.ville ?? "").trim();
          if (!v) continue;
          const a = (par[v] ??= { n: 0, somme: 0, nbScore: 0, top: 0, rep: 0 });
          a.n++;
          if (typeof l.score === "number") {
            a.somme += l.score;
            a.nbScore++;
            if (l.score >= 75) a.top++;
          }
          if (l.statut === "repondu") a.rep++;
        }
        const rows = Object.entries(par)
          .map(([ville, a]) => ({
            ville,
            leads: a.n,
            score_moyen: a.nbScore ? Math.round(a.somme / a.nbScore) : null,
            top_leads: a.top,
            reponses: a.rep,
          }))
          .sort((x, y) => y.top_leads - x.top_leads || y.leads - x.leads)
          .slice(0, 12);
        if (rows.length === 0) return "Pas encore de données par localité.";
        return JSON.stringify(rows);
      }

      case "lister_zones_cibles": {
        const { data, error } = await supabase
          .from("zones_cibles")
          .select("nom, adresse, rayon_km")
          .order("created_at", { ascending: false });
        if (error) return `Erreur: ${error.message}`;
        const zones = (data as { nom: string; adresse: string; rayon_km: number }[]) ?? [];
        if (zones.length === 0)
          return "Aucune zone enregistrée. En créer dans l'onglet Recherches (mode adresse).";
        return JSON.stringify(zones);
      }

      case "analyser_satellite": {
        const nom = typeof input.entreprise === "string" ? input.entreprise.trim() : "";
        if (!nom) return "Précise le nom de l'entreprise.";
        const { data, error } = await supabase
          .from("leads")
          .select("id, entreprise")
          .ilike("entreprise", `%${nom}%`)
          .limit(1)
          .maybeSingle();
        if (error) return `Erreur: ${error.message}`;
        if (!data) return `Aucun lead trouvé pour "${nom}".`;
        const res = await analyseSatellite(supabase, data.id as string);
        if ("error" in res) return res.error;
        return JSON.stringify({ entreprise: data.entreprise, ...res.result });
      }

      default:
        return `Outil inconnu : ${name}`;
    }
  } catch (e) {
    return `Erreur lors de l'exécution: ${e instanceof Error ? e.message : "inconnue"}`;
  }
}
