import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { analyseSatellite } from "@/lib/satellite";
import type { AgentConfig, Run, Verticale } from "@/lib/database.types";

const SATELLITE_PAR_TICK = 5;
const RELANCES_PAR_TICK = 10;

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

  // Passe relance (Palier 3.1) : planifie les relances dues sans rien envoyer.
  // Garde-fou cardinal — « jamais d'action sortante sans validation » : l'agent
  // ne fait que poser statut=a_relancer + relance_at pour remplir la worklist ;
  // l'humain valide et envoie. Indépendant du budget des runs (coût nul).
  if (cfg.relance_auto) {
    const seuilISO = new Date(
      Date.now() - cfg.relance_delai_jours * 86_400_000,
    ).toISOString();
    const { data: candidats } = await admin
      .from("leads")
      .select("id")
      .in("statut", ["envoye", "ouvert"])
      .is("relance_at", null)
      .is("bounced_at", null)
      .not("sent_at", "is", null)
      .lt("sent_at", seuilISO)
      .order("score", { ascending: false, nullsFirst: false })
      .limit(RELANCES_PAR_TICK);

    let relancesPlanifiees = 0;
    for (const l of (candidats as { id: string }[]) ?? []) {
      // Garde-fou anti-harcèlement : on compte les relances déjà tracées.
      const { count } = await admin
        .from("lead_events")
        .select("id", { count: "exact", head: true })
        .eq("lead_id", l.id)
        .eq("type", "relance");
      if ((count ?? 0) >= cfg.relance_max) continue;

      const { error: upErr } = await admin
        .from("leads")
        .update({ statut: "a_relancer", relance_at: new Date().toISOString() })
        .eq("id", l.id);
      if (upErr) continue;
      await admin.from("lead_events").insert({
        lead_id: l.id,
        type: "relance",
        payload: { auto: true },
      });
      relancesPlanifiees++;
    }
    if (relancesPlanifiees > 0) {
      await admin.from("agent_journal").insert({
        type: "relance_auto",
        message: `Relances planifiées automatiquement : ${relancesPlanifiees} lead(s) sans réponse depuis ${cfg.relance_delai_jours} j. (à valider et envoyer)`,
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
