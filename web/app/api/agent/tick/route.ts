import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { analyseSatellite } from "@/lib/satellite";
import { generateOutreachDraft } from "@/lib/outreach";
import type { AgentConfig, Run, Verticale } from "@/lib/database.types";

const SATELLITE_PAR_TICK = 5;
const RELANCES_PAR_TICK = 10;
// Plafond dur de conversions veille→lead par tick : chaque conversion consomme
// un appel IA (pré-rédaction). Garde-fou budget.
const VEILLE_AUTO_PAR_TICK = 3;

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Tick de l'agent autonome. Appelé par le cron Vercel.
// Lance au plus une recherche par tick, dans les limites du mandat.
async function handle(req: NextRequest) {
  // Auth : header Vercel Cron (CRON_SECRET) ou secret en query.
  const auth = req.headers.get("authorization");
  const querySecret = req.nextUrl.searchParams.get("secret");
  const cronSecret = process.env.CRON_SECRET;
  const agentSecret = process.env.AGENT_CRON_SECRET;
  const ok =
    (cronSecret && auth === `Bearer ${cronSecret}`) ||
    (agentSecret && querySecret === agentSecret);
  if (!ok) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const admin = createAdminClient();
  if (!admin) {
    return NextResponse.json({ error: "service role manquante" }, { status: 500 });
  }

  const { data: cfgData } = await admin
    .from("agent_config")
    .select("*")
    .order("created_at", { ascending: true })
    .limit(1)
    .maybeSingle();
  const cfg = cfgData as AgentConfig | null;
  if (!cfg) return NextResponse.json({ skipped: "no_config" });
  if (!cfg.autonomie) return NextResponse.json({ skipped: "disabled" });

  // Passe satellite : analyse quelques leads non encore analysés (si activé).
  let satelliteAnalyses = 0;
  if (cfg.satellite_auto) {
    const { data: aAnalyser } = await admin
      .from("leads")
      .select("id")
      .is("vision_satellite", null)
      .not("latitude", "is", null)
      .neq("statut", "ecarte")
      .order("score", { ascending: false, nullsFirst: false })
      .limit(SATELLITE_PAR_TICK);
    for (const l of (aAnalyser as { id: string }[]) ?? []) {
      const r = await analyseSatellite(admin, l.id);
      if ("ok" in r) satelliteAnalyses++;
    }
    if (satelliteAnalyses > 0) {
      await admin.from("agent_journal").insert({
        type: "info",
        message: `Analyse satellite auto : ${satelliteAnalyses} lead(s).`,
      });
    }
  }

  // Passe relance (Palier 3.1) + cadence multi-canal (Palier 3.2) : planifie les
  // relances dues sans rien envoyer, et quand le canal mail est épuisé (plafond
  // relance_max atteint sans réponse) escalade vers le téléphone (call_statut
  // a_appeler) si un numéro existe. Garde-fou cardinal — « jamais d'action
  // sortante sans validation » : l'agent ne fait que remplir les worklists
  // (« À relancer », « À appeler ») ; l'humain valide, envoie et appelle.
  // Indépendant du budget des runs (coût nul).
  if (cfg.relance_auto) {
    // Budget journalier (garde-fou « auto sous limites ») : on ne planifie pas
    // plus de relances que le quota du jour, tous leads et tous ticks confondus.
    const sodRelance = new Date();
    sodRelance.setHours(0, 0, 0, 0);
    const { count: dejaAuj } = await admin
      .from("lead_events")
      .select("id", { count: "exact", head: true })
      .eq("type", "relance")
      .eq("payload->>auto", "true")
      .gte("at", sodRelance.toISOString());
    const budgetRestant = Math.max(0, cfg.relance_auto_max_jour - (dejaAuj ?? 0));

    if (budgetRestant === 0) {
      await admin.from("agent_journal").insert({
        type: "skip_relance_budget",
        message: `Budget de relances du jour atteint (${cfg.relance_auto_max_jour}/j).`,
      });
    } else {
      const seuilISO = new Date(
        Date.now() - cfg.relance_delai_jours * 86_400_000,
      ).toISOString();
      const aTraiter = Math.min(RELANCES_PAR_TICK, budgetRestant);
      const { data: candidats } = await admin
        .from("leads")
        .select(
          "id, contact_tel, call_statut, entreprise, ville, libelle_naf, effectif, contact_nom, score_raison, vision_satellite",
        )
        .in("statut", ["envoye", "ouvert"])
        .is("relance_at", null)
        .is("bounced_at", null)
        .not("sent_at", "is", null)
        .lt("sent_at", seuilISO)
        .order("score", { ascending: false, nullsFirst: false })
        .limit(aTraiter);

      // Pré-rédaction (autonomie sous budget) : on prépare le brouillon de relance,
      // jamais envoyé. Désactivable, et sans clé IA on se contente de planifier.
      const apiKey = process.env.ANTHROPIC_API_KEY;
      const predraft = cfg.relance_predraft && Boolean(apiKey);
      let calendlyUrl: string | null = null;
      if (predraft) {
        const { data: ctx } = await admin
          .from("app_context")
          .select("calendly_url")
          .eq("id", "main")
          .maybeSingle();
        calendlyUrl = (ctx as { calendly_url: string | null } | null)?.calendly_url ?? null;
      }

      let relancesPlanifiees = 0;
      let relancesRedigees = 0;
      let escaladesAppel = 0;
      type Cand = {
        id: string;
        contact_tel: string | null;
        call_statut: string | null;
        entreprise: string;
        ville: string | null;
        libelle_naf: string | null;
        effectif: string | null;
        contact_nom: string | null;
        score_raison: string | null;
        vision_satellite: Record<string, unknown> | null;
      };
      for (const l of (candidats as Cand[]) ?? []) {
        // Garde-fou anti-harcèlement : on compte les relances déjà tracées.
        const { count } = await admin
          .from("lead_events")
          .select("id", { count: "exact", head: true })
          .eq("lead_id", l.id)
          .eq("type", "relance");
        if ((count ?? 0) >= cfg.relance_max) {
          // Canal mail épuisé → escalade téléphone (sans appeler), une seule fois.
          if (l.contact_tel && !l.call_statut) {
            const { error: callErr } = await admin
              .from("leads")
              .update({ call_statut: "a_appeler" })
              .eq("id", l.id);
            if (!callErr) {
              await admin.from("lead_events").insert({
                lead_id: l.id,
                type: "note",
                payload: { action: "escalade_appel", auto: true },
              });
              escaladesAppel++;
            }
          }
          continue;
        }

        const { error: upErr } = await admin
          .from("leads")
          .update({ statut: "a_relancer", relance_at: new Date().toISOString() })
          .eq("id", l.id);
        if (upErr) continue;

        // Brouillon de relance prêt à valider (jamais envoyé).
        let redige = false;
        if (predraft) {
          const draft = await generateOutreachDraft(
            apiKey!,
            "relance",
            {
              entreprise: l.entreprise,
              ville: l.ville,
              secteur: l.libelle_naf,
              effectif: l.effectif,
              contact_nom: l.contact_nom,
              score_raison: l.score_raison,
              vision: l.vision_satellite,
            },
            null,
            calendlyUrl,
          );
          if (draft.ok) {
            await admin
              .from("leads")
              .update({ mail_sujet: draft.sujet, mail_corps: draft.corps })
              .eq("id", l.id);
            redige = true;
            relancesRedigees++;
          }
        }

        await admin.from("lead_events").insert({
          lead_id: l.id,
          type: "relance",
          payload: { auto: true, predraft: redige },
        });
        relancesPlanifiees++;
      }
      if (relancesPlanifiees > 0) {
        const suffixe = relancesRedigees
          ? ` dont ${relancesRedigees} avec brouillon de relance prêt`
          : "";
        await admin.from("agent_journal").insert({
          type: "relance_auto",
          message: `Relances planifiées : ${relancesPlanifiees} lead(s) sans réponse depuis ${cfg.relance_delai_jours} j.${suffixe} (à valider et envoyer · budget ${cfg.relance_auto_max_jour}/j).`,
        });
      }
      if (escaladesAppel > 0) {
        await admin.from("agent_journal").insert({
          type: "escalade_appel",
          message: `Canal mail épuisé : ${escaladesAppel} lead(s) basculé(s) « à appeler » (relances mail au plafond). À appeler depuis l'inbox.`,
        });
      }
    }
  }

  // Passe speed-to-lead (incrément D) : les signaux de veille les plus chauds
  // (score d'intention ≥ seuil) sont convertis en leads « à valider » et leur
  // approche est pré-rédigée. Aucun envoi — l'humain valide et envoie. Plafonné.
  if (cfg.veille_auto_lead) {
    const { data: signaux } = await admin
      .from("veille_signaux")
      .select(
        "id, entreprise, ville, declencheur, angle, resume, source_url, score_intention, score_fit",
      )
      .eq("statut", "nouveau")
      .gte("score_intention", cfg.veille_auto_seuil)
      .order("score_intention", { ascending: false, nullsFirst: false })
      .limit(VEILLE_AUTO_PAR_TICK);

    type Sig = {
      id: string;
      entreprise: string;
      ville: string | null;
      declencheur: string | null;
      angle: string | null;
      resume: string | null;
      source_url: string | null;
      score_intention: number | null;
      score_fit: number | null;
    };
    const sigs = (signaux as Sig[]) ?? [];

    const apiKey = process.env.ANTHROPIC_API_KEY;
    let calendlyUrl: string | null = null;
    if (apiKey && sigs.length > 0) {
      const { data: ctx } = await admin
        .from("app_context")
        .select("calendly_url")
        .eq("id", "main")
        .maybeSingle();
      calendlyUrl = (ctx as { calendly_url: string | null } | null)?.calendly_url ?? null;
    }

    let veilleConvertis = 0;
    for (const s of sigs) {
      const raison =
        [s.declencheur, s.angle].filter(Boolean).join(" — ") ||
        s.resume ||
        "Signal de veille";
      const { data: lead, error: insErr } = await admin
        .from("leads")
        .insert({
          entreprise: s.entreprise,
          ville: s.ville ?? null,
          adresse: s.ville ?? null,
          score: s.score_intention ?? s.score_fit ?? null,
          score_raison: `Veille — ${raison}`,
          site_web: s.source_url ?? null,
          statut: "a_valider",
        })
        .select("id")
        .single();
      if (insErr || !lead) continue;
      await admin
        .from("veille_signaux")
        .update({ statut: "converti", lead_id: lead.id })
        .eq("id", s.id);

      // Pré-rédaction de l'approche (si IA dispo) — persistée, jamais envoyée.
      if (apiKey) {
        const draft = await generateOutreachDraft(
          apiKey,
          "approche",
          {
            entreprise: s.entreprise,
            ville: s.ville,
            secteur: null,
            effectif: null,
            contact_nom: null,
            score_raison: `Veille — ${raison}`,
            vision: null,
          },
          null,
          calendlyUrl,
        );
        if (draft.ok) {
          await admin
            .from("leads")
            .update({ mail_sujet: draft.sujet, mail_corps: draft.corps })
            .eq("id", lead.id);
        }
      }
      veilleConvertis++;
    }
    if (veilleConvertis > 0) {
      await admin.from("agent_journal").insert({
        type: "veille_auto",
        message: `Veille → lead : ${veilleConvertis} signal(aux) chaud(s) converti(s) en lead(s) « à valider » + approche pré-rédigée. À valider dans l'inbox.`,
      });
    }
  }

  const startOfDay = new Date();
  startOfDay.setHours(0, 0, 0, 0);

  // Runs lancés aujourd'hui (pour cadence budget + nombre).
  const { data: runsToday } = await admin
    .from("runs")
    .select("id, budget_eur, created_at")
    .gte("created_at", startOfDay.toISOString());
  const launchedToday = (runsToday as Partial<Run>[]) ?? [];

  if (launchedToday.length >= cfg.max_runs_jour) {
    return NextResponse.json({ skipped: "max_runs_jour" });
  }

  const budgetEngage = launchedToday.reduce(
    (s, r) => s + Number(r.budget_eur ?? 0),
    0,
  );
  const budgetRun = Number(cfg.budget_run_eur);
  if (budgetEngage + budgetRun > Number(cfg.budget_jour_eur)) {
    await admin.from("agent_journal").insert({
      type: "skip_budget",
      message: `Plafond journalier atteint (${budgetEngage}€ engagés + ${budgetRun}€ > ${cfg.budget_jour_eur}€).`,
    });
    return NextResponse.json({ skipped: "budget" });
  }

  // Cadence : intervalle minimum depuis le dernier lancement auto.
  const { data: lastLaunch } = await admin
    .from("agent_journal")
    .select("at")
    .eq("type", "run_lance")
    .order("at", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (lastLaunch?.at) {
    const elapsedMin = (Date.now() - new Date(lastLaunch.at).getTime()) / 60000;
    if (elapsedMin < cfg.cadence_min) {
      return NextResponse.json({ skipped: "cadence", elapsedMin });
    }
  }

  // Périmètre : départements obligatoires.
  if (cfg.departements.length === 0) {
    return NextResponse.json({ skipped: "aucun_departement" });
  }

  // Cibles : celles du mandat, sinon toutes les actives.
  let cibleIds = cfg.cibles_autorisees;
  if (cibleIds.length === 0) {
    const { data: vData } = await admin
      .from("verticales")
      .select("id")
      .eq("active", true)
      .order("nom");
    cibleIds = ((vData as Pick<Verticale, "id">[]) ?? []).map((v) => v.id);
  }
  if (cibleIds.length === 0) {
    return NextResponse.json({ skipped: "aucune_cible" });
  }

  // Rotation simple cible × département selon le nombre déjà lancé aujourd'hui.
  const idx = launchedToday.length;
  const departement = cfg.departements[idx % cfg.departements.length];
  const verticaleId = cibleIds[idx % cibleIds.length];

  const { data: run, error: runErr } = await admin
    .from("runs")
    .insert({
      verticale_id: verticaleId,
      zone: { departement, effectif_min: cfg.effectif_min },
      volume_cible: cfg.volume_run,
      budget_eur: budgetRun,
      status: "demande",
      created_by: null,
    })
    .select("id")
    .single();
  if (runErr) {
    await admin.from("agent_journal").insert({
      type: "erreur",
      message: `Échec du lancement auto : ${runErr.message}`,
    });
    return NextResponse.json({ error: runErr.message }, { status: 500 });
  }

  await admin.from("agent_journal").insert({
    type: "run_lance",
    run_id: run.id,
    cout_estime_eur: budgetRun,
    message: `Recherche lancée automatiquement (dépt ${departement}, budget ${budgetRun}€).`,
    payload: { departement, verticale_id: verticaleId, auto: true },
  });

  return NextResponse.json({ launched: true, run_id: run.id, departement });
}

export async function GET(req: NextRequest) {
  return handle(req);
}

export async function POST(req: NextRequest) {
  return handle(req);
}
