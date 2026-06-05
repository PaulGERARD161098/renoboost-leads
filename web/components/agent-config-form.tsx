"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { updateAgentConfig } from "@/lib/actions/agent";
import type { AgentConfig, Verticale } from "@/lib/database.types";

export function AgentConfigForm({
  config,
  verticales,
}: {
  config: AgentConfig;
  verticales: Pick<Verticale, "id" | "nom">[];
}) {
  const router = useRouter();
  const [autonomie, setAutonomie] = useState(config.autonomie);
  const [satelliteAuto, setSatelliteAuto] = useState(config.satellite_auto);
  const [cibles, setCibles] = useState<string[]>(config.cibles_autorisees);
  const [departements, setDepartements] = useState(
    config.departements.join(", "),
  );
  const [budgetJour, setBudgetJour] = useState(String(config.budget_jour_eur));
  const [budgetRun, setBudgetRun] = useState(String(config.budget_run_eur));
  const [volume, setVolume] = useState(String(config.volume_run));
  const [effectifMin, setEffectifMin] = useState(
    config.effectif_min === null ? "" : String(config.effectif_min),
  );
  const [maxRuns, setMaxRuns] = useState(String(config.max_runs_jour));
  const [cadence, setCadence] = useState(String(config.cadence_min));
  const [relanceAuto, setRelanceAuto] = useState(config.relance_auto);
  const [relanceDelai, setRelanceDelai] = useState(
    String(config.relance_delai_jours),
  );
  const [relanceMax, setRelanceMax] = useState(String(config.relance_max));
  const [reponseStatutAuto, setReponseStatutAuto] = useState(
    config.reponse_statut_auto,
  );
  const [veilleAutoLead, setVeilleAutoLead] = useState(config.veille_auto_lead);
  const [veilleAutoSeuil, setVeilleAutoSeuil] = useState(
    String(config.veille_auto_seuil),
  );
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  function toggleCible(id: string) {
    setCibles((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));
  }

  async function save() {
    setSaving(true);
    setMsg(null);
    const res = await updateAgentConfig({
      id: config.id,
      autonomie,
      cibles_autorisees: cibles,
      departements: departements
        .split(",")
        .map((d) => d.trim())
        .filter(Boolean),
      budget_jour_eur: Number(budgetJour) || 0,
      budget_run_eur: Number(budgetRun) || 0,
      volume_run: Number(volume) || 0,
      effectif_min: effectifMin.trim() ? Number(effectifMin) : null,
      max_runs_jour: Number(maxRuns) || 0,
      cadence_min: Number(cadence) || 0,
      satellite_auto: satelliteAuto,
      relance_auto: relanceAuto,
      relance_delai_jours: Number(relanceDelai) || 0,
      relance_max: Number(relanceMax) || 0,
      reponse_statut_auto: reponseStatutAuto,
      veille_auto_lead: veilleAutoLead,
      veille_auto_seuil: Number(veilleAutoSeuil) || 0,
    });
    setSaving(false);
    if (res.error) setMsg(`Erreur : ${res.error}`);
    else {
      setMsg("Mandat enregistré.");
      router.refresh();
    }
  }

  return (
    <div className="space-y-6">
      {/* Autonomie */}
      <div className="flex items-center justify-between rounded-xl border border-[var(--border)] bg-white p-4">
        <div>
          <div className="font-semibold">Autonomie de l&apos;agent</div>
          <div className="text-sm text-[var(--muted)]">
            Si activée, Magellan lance des recherches tout seul, dans les limites
            ci-dessous — même quand tu n&apos;es pas connecté.
          </div>
        </div>
        <button
          onClick={() => setAutonomie((a) => !a)}
          className={`relative h-7 w-12 shrink-0 rounded-full transition ${
            autonomie ? "bg-[var(--brand)]" : "bg-slate-300"
          }`}
          aria-pressed={autonomie}
        >
          <span
            className={`absolute top-0.5 h-6 w-6 rounded-full bg-white shadow transition ${
              autonomie ? "left-[1.375rem]" : "left-0.5"
            }`}
          />
        </button>
      </div>

      {/* Analyse satellite auto */}
      <div className="flex items-center justify-between rounded-xl border border-[var(--border)] bg-white p-4">
        <div>
          <div className="font-semibold">Analyse satellite automatique</div>
          <div className="text-sm text-[var(--muted)]">
            L&apos;agent analyse aussi le potentiel solaire (toiture/parking) des
            meilleurs leads non encore analysés, par petits lots.
          </div>
        </div>
        <button
          onClick={() => setSatelliteAuto((a) => !a)}
          className={`relative h-7 w-12 shrink-0 rounded-full transition ${
            satelliteAuto ? "bg-[var(--brand)]" : "bg-slate-300"
          }`}
          aria-pressed={satelliteAuto}
        >
          <span
            className={`absolute top-0.5 h-6 w-6 rounded-full bg-white shadow transition ${
              satelliteAuto ? "left-[1.375rem]" : "left-0.5"
            }`}
          />
        </button>
      </div>

      {/* Relances automatiques (sous garde-fous, sans envoi) */}
      <div className="rounded-xl border border-[var(--border)] bg-white p-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-semibold">Relances automatiques (multi-canal)</div>
            <div className="text-sm text-[var(--muted)]">
              L&apos;agent repère les envois restés sans réponse et{" "}
              <strong>planifie la relance</strong> (colonne « À relancer »). Une
              fois le mail épuisé, il <strong>escalade vers le téléphone</strong>{" "}
              (« À appeler ») — il n&apos;envoie ni n&apos;appelle jamais : tu
              valides, tu envoies, tu appelles.
            </div>
          </div>
          <button
            onClick={() => setRelanceAuto((a) => !a)}
            className={`relative h-7 w-12 shrink-0 rounded-full transition ${
              relanceAuto ? "bg-[var(--brand)]" : "bg-slate-300"
            }`}
            aria-pressed={relanceAuto}
          >
            <span
              className={`absolute top-0.5 h-6 w-6 rounded-full bg-white shadow transition ${
                relanceAuto ? "left-[1.375rem]" : "left-0.5"
              }`}
            />
          </button>
        </div>
        {relanceAuto && (
          <div className="mt-4 grid grid-cols-2 gap-4">
            <Field
              label="Délai sans réponse avant relance (jours)"
              value={relanceDelai}
              onChange={setRelanceDelai}
            />
            <Field
              label="Relances max. par lead"
              value={relanceMax}
              onChange={setRelanceMax}
            />
          </div>
        )}
      </div>

      {/* Transitions de statut sur réponse (conservateur) */}
      <div className="flex items-center justify-between rounded-xl border border-[var(--border)] bg-white p-4">
        <div>
          <div className="font-semibold">Statut auto sur réponse</div>
          <div className="text-sm text-[var(--muted)]">
            Quand Magellan classe une réponse, applique les transitions{" "}
            <strong>sûres</strong> tout seul (« plus tard » → relance planifiée à
            +3 sem.). Les écartements (refus, absence, mauvais interlocuteur)
            restent <strong>proposés en 1 clic</strong>, jamais automatiques.
          </div>
        </div>
        <button
          onClick={() => setReponseStatutAuto((a) => !a)}
          className={`relative h-7 w-12 shrink-0 rounded-full transition ${
            reponseStatutAuto ? "bg-[var(--brand)]" : "bg-slate-300"
          }`}
          aria-pressed={reponseStatutAuto}
        >
          <span
            className={`absolute top-0.5 h-6 w-6 rounded-full bg-white shadow transition ${
              reponseStatutAuto ? "left-[1.375rem]" : "left-0.5"
            }`}
          />
        </button>
      </div>

      {/* Speed-to-lead : veille chaude → lead + pré-rédaction */}
      <div className="rounded-xl border border-[var(--border)] bg-white p-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-semibold">Veille chaude → lead automatique</div>
            <div className="text-sm text-[var(--muted)]">
              Les signaux de veille dont l&apos;intention dépasse le seuil sont{" "}
              <strong>convertis en leads « à valider »</strong> et leur approche
              est <strong>pré-rédigée</strong> — tu valides et envoies. Aucun
              envoi automatique.
            </div>
          </div>
          <button
            onClick={() => setVeilleAutoLead((a) => !a)}
            className={`relative h-7 w-12 shrink-0 rounded-full transition ${
              veilleAutoLead ? "bg-[var(--brand)]" : "bg-slate-300"
            }`}
            aria-pressed={veilleAutoLead}
          >
            <span
              className={`absolute top-0.5 h-6 w-6 rounded-full bg-white shadow transition ${
                veilleAutoLead ? "left-[1.375rem]" : "left-0.5"
              }`}
            />
          </button>
        </div>
        {veilleAutoLead && (
          <div className="mt-4 grid grid-cols-2 gap-4">
            <Field
              label="Score d'intention minimum (0-100)"
              value={veilleAutoSeuil}
              onChange={setVeilleAutoSeuil}
            />
          </div>
        )}
      </div>

      {/* Périmètre */}
      <Card titre="Périmètre autorisé">
        <Label>Cibles autorisées (aucune cochée = toutes les cibles actives)</Label>
        <div className="mb-4 flex flex-wrap gap-2">
          {verticales.length === 0 && (
            <span className="text-sm text-[var(--muted)]">
              Aucune cible active. Crée-en dans l&apos;onglet Cibles.
            </span>
          )}
          {verticales.map((v) => (
            <button
              key={v.id}
              onClick={() => toggleCible(v.id)}
              className={`rounded-full border px-3 py-1 text-sm ${
                cibles.includes(v.id)
                  ? "border-[var(--brand)] bg-[var(--brand)] text-white"
                  : "border-[var(--border)] text-[var(--muted)] hover:bg-slate-100"
              }`}
            >
              {v.nom}
            </button>
          ))}
        </div>
        <Label>Départements autorisés (séparés par des virgules, ex : 59, 62, 75)</Label>
        <input
          value={departements}
          onChange={(e) => setDepartements(e.target.value)}
          placeholder="59, 62, 75"
          className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
        />
      </Card>

      {/* Budget & cadence */}
      <Card titre="Budget & cadence">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
          <Field label="Budget / jour (€) — plafond bloquant" value={budgetJour} onChange={setBudgetJour} />
          <Field label="Budget / recherche (€)" value={budgetRun} onChange={setBudgetRun} />
          <Field label="Volume visé / recherche" value={volume} onChange={setVolume} />
          <Field label="Max recherches / jour" value={maxRuns} onChange={setMaxRuns} />
          <Field label="Cadence min. entre 2 (minutes)" value={cadence} onChange={setCadence} />
          <Field label="Effectif min. (optionnel)" value={effectifMin} onChange={setEffectifMin} />
        </div>
      </Card>

      <div className="flex items-center gap-4">
        <button
          onClick={save}
          disabled={saving}
          className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {saving ? "Enregistrement…" : "Enregistrer le mandat"}
        </button>
        {msg && <span className="text-sm text-[var(--muted)]">{msg}</span>}
      </div>
    </div>
  );
}

function Card({ titre, children }: { titre: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-white p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
        {titre}
      </h2>
      {children}
    </div>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <div className="mb-1 text-sm font-medium">{children}</div>;
}

function Field({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-[var(--muted)]">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        inputMode="numeric"
        className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
      />
    </label>
  );
}
