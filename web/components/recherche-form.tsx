"use client";

import { useState, useTransition } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createRun } from "@/lib/actions/runs";
import { createZoneCible, deleteZoneCible } from "@/lib/actions/zones";
import type { Verticale, ZoneCible } from "@/lib/database.types";
import { estimerCoutRun, formatEur } from "@/lib/costs";
import { intentionsDeConfig } from "@/lib/intentions";
import {
  EFFECTIF_DEFAUT,
  EFFECTIF_PRESETS,
  type EffectifPresetId,
  effectifLabel,
  presetParId,
  presetPour,
  validerCiblage,
} from "@/lib/run-targeting";

export type RechercheInitial = {
  verticaleId?: string;
  mode?: "departement" | "adresse";
  departement?: string;
  adresse?: string;
  rayon?: string;
  effectifMin?: string;
  effectifMax?: string;
  volume?: string;
  budget?: string;
  isTest?: boolean;
};

/** Presets de volume rapides (le moteur s'arrête au volume atteint OU au budget). */
const VOLUME_PRESETS = [100, 500, 1000] as const;

export function RechercheForm({
  verticales,
  zones = [],
  initial,
}: {
  verticales: Verticale[];
  zones?: ZoneCible[];
  initial?: RechercheInitial;
}) {
  const router = useRouter();
  const [verticaleId, setVerticaleId] = useState(
    initial?.verticaleId ?? verticales[0]?.id ?? "",
  );
  const [mode, setMode] = useState<"departement" | "adresse">(
    initial?.mode ?? "departement",
  );
  const [departement, setDepartement] = useState(initial?.departement ?? "59");
  const [adresse, setAdresse] = useState(initial?.adresse ?? "");
  const [rayon, setRayon] = useState(initial?.rayon ?? "10");
  const [nomZone, setNomZone] = useState("");
  // Effectif : tranche par preset (PME 10–250 par défaut), avec min/max libres en
  // mode « Personnalisé ». Pré-rempli depuis un run relancé si min/max fournis.
  const initMin =
    initial?.effectifMin != null && initial.effectifMin !== ""
      ? Number(initial.effectifMin)
      : null;
  const initMax =
    initial?.effectifMax != null && initial.effectifMax !== ""
      ? Number(initial.effectifMax)
      : null;
  const [effectifPreset, setEffectifPreset] = useState<EffectifPresetId>(
    initMin != null || initMax != null ? presetPour(initMin, initMax) : EFFECTIF_DEFAUT,
  );
  const [effectifMinCustom, setEffectifMinCustom] = useState(
    initMin != null ? String(initMin) : "",
  );
  const [effectifMaxCustom, setEffectifMaxCustom] = useState(
    initMax != null ? String(initMax) : "",
  );
  const [volume, setVolume] = useState(initial?.volume ?? "200");
  const [budget, setBudget] = useState(initial?.budget ?? "50");
  const [isTest, setIsTest] = useState(initial?.isTest ?? false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  // Tranche d'effectif effective (preset, ou min/max libres si « Personnalisé »).
  const preset = presetParId(effectifPreset);
  const effMin =
    effectifPreset === "custom"
      ? effectifMinCustom.trim()
        ? Number(effectifMinCustom)
        : null
      : preset.min;
  const effMax =
    effectifPreset === "custom"
      ? effectifMaxCustom.trim()
        ? Number(effectifMaxCustom)
        : null
      : preset.max;

  // Estimation de coût (garde-fou budget) — recalculée à chaque changement.
  const volumeNum = Number(volume) || 0;
  const budgetNum = Number(budget) || 0;
  const estimation = estimerCoutRun(volumeNum);
  const budgetInsuffisant =
    !isTest && budgetNum > 0 && estimation.bas > budgetNum;
  // Garde-fous (bloquant + alertes) consolidés pour la modale de validation.
  const verdict = validerCiblage({
    effectifMin: effMin,
    effectifMax: effMax,
    volume: volume ? Number(volume) : null,
    budgetEur: budget ? Number(budget) : null,
    coutEstimeBas: estimation.bas,
    isTest,
  });
  const [msg, setMsg] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function appliquerZone(id: string) {
    const z = zones.find((x) => x.id === id);
    if (z) {
      setAdresse(z.adresse);
      setRayon(String(z.rayon_km));
    }
  }

  function enregistrerZone() {
    if (!adresse.trim() || !nomZone.trim()) {
      setMsg("❌ Donne un nom et une adresse pour enregistrer la zone.");
      return;
    }
    startTransition(async () => {
      const res = await createZoneCible({
        nom: nomZone,
        adresse,
        rayonKm: Number(rayon) || 10,
      });
      if (res.error) setMsg(`❌ ${res.error}`);
      else {
        setNomZone("");
        setMsg("✅ Zone enregistrée.");
        router.refresh();
      }
    });
  }

  function supprimerZone(id: string) {
    startTransition(async () => {
      await deleteZoneCible(id);
      router.refresh();
    });
  }

  // Submit = validation puis RÉCAP (modale). On ne lance jamais sans confirmation.
  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (mode === "adresse" && !adresse.trim()) {
      setMsg("❌ Renseigne une adresse (centre de la zone).");
      return;
    }
    if (verdict.erreurs.length > 0) {
      setMsg(`❌ ${verdict.erreurs.join(" ")}`);
      return;
    }
    setMsg(null);
    setConfirmOpen(true);
  }

  // Lancement réel, déclenché par le bouton « Confirmer » de la modale.
  function confirmer() {
    setConfirmOpen(false);
    setMsg(null);
    startTransition(async () => {
      const res = await createRun({
        verticaleId,
        departement: mode === "departement" ? departement : null,
        adresse: mode === "adresse" ? adresse : null,
        rayonKm: mode === "adresse" ? Number(rayon) || 10 : null,
        effectifMin: effMin,
        effectifMax: effMax,
        volumeCible: volume ? Number(volume) : null,
        budgetEur: budget ? Number(budget) : null,
        isTest,
      });
      if (res.error) setMsg(`❌ ${res.error}`);
      else
        setMsg(
          isTest
            ? "✅ Recherche test demandée (mode démo, gratuit). Les faux prospects apparaîtront dans Prospects."
            : "✅ Recherche demandée. Le moteur la traitera ; les prospects apparaîtront dans Prospects.",
        );
    });
  }

  const cibleSelectionnee = verticales.find((v) => v.id === verticaleId);
  const cibleNom = cibleSelectionnee?.nom ?? "—";
  const intentions = intentionsDeConfig(cibleSelectionnee?.config);

  return (
    <>
    <form
      onSubmit={submit}
      className="max-w-lg space-y-4 rounded-xl border border-[var(--border)] bg-white p-6"
    >
      <div>
        <label className="mb-1 block text-sm font-medium">Cible</label>
        <select
          value={verticaleId}
          onChange={(e) => setVerticaleId(e.target.value)}
          className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
        >
          {verticales.map((v) => (
            <option key={v.id} value={v.id}>
              {v.nom}
            </option>
          ))}
        </select>
        {/* Contexte : les intentions de la Cible pilotent le ciblage (NAF +
            signaux) de cette recherche. Transparence intentions ⟶ recherche. */}
        {intentions.length > 0 ? (
          <div className="mt-2 rounded-lg bg-[var(--brand)]/5 px-3 py-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs font-medium text-[var(--muted)]">
                🎯 Cible l&apos;intention :
              </span>
              {intentions.map((i) => (
                <span
                  key={i.id}
                  className="rounded bg-[var(--brand)]/10 px-1.5 py-0.5 text-xs font-medium text-[var(--brand)]"
                  title={i.description}
                >
                  {i.label}
                </span>
              ))}
            </div>
            <p className="mt-1 text-xs text-[var(--muted)]">
              Secteurs NAF et signaux recherchés en découlent.{" "}
              <Link
                href={`/cibles/${verticaleId}`}
                className="text-[var(--brand)] hover:underline"
              >
                Ajuster la cible →
              </Link>
            </p>
          </div>
        ) : (
          verticaleId && (
            <p className="mt-2 text-xs text-[var(--muted)]">
              Aucune intention déclarée sur cette cible.{" "}
              <Link
                href={`/cibles/${verticaleId}`}
                className="text-[var(--brand)] hover:underline"
              >
                En ajouter →
              </Link>{" "}
              affine le ciblage.
            </p>
          )
        )}
      </div>

      {/* Mode de zone */}
      <div>
        <label className="mb-1 block text-sm font-medium">Zone ciblée</label>
        <div className="flex gap-2">
          {(["departement", "adresse"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={`flex-1 rounded-lg border px-3 py-1.5 text-sm font-medium transition ${
                mode === m
                  ? "border-[var(--brand)] bg-[var(--brand)] text-white"
                  : "border-[var(--border)] text-[var(--muted)] hover:bg-slate-50"
              }`}
            >
              {m === "departement" ? "Par département" : "Autour d'une adresse"}
            </button>
          ))}
        </div>
      </div>

      {mode === "departement" ? (
        <div>
          <label className="mb-1 block text-sm font-medium">Département</label>
          <input
            value={departement}
            onChange={(e) => setDepartement(e.target.value)}
            placeholder="59"
            className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
          />
        </div>
      ) : (
        <div className="space-y-3">
          {zones.length > 0 && (
            <div>
              <label className="mb-1 block text-sm font-medium">
                Zone enregistrée
              </label>
              <select
                defaultValue=""
                onChange={(e) => appliquerZone(e.target.value)}
                className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
              >
                <option value="">— Choisir une zone enregistrée —</option>
                {zones.map((z) => (
                  <option key={z.id} value={z.id}>
                    {z.nom} ({z.rayon_km} km)
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="grid grid-cols-[1fr_auto] gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium">
                Adresse (centre de la zone)
              </label>
              <input
                value={adresse}
                onChange={(e) => setAdresse(e.target.value)}
                placeholder="ex : Zone d'activité de Wambrechies, 59118"
                className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Rayon (km)</label>
              <input
                type="number"
                value={rayon}
                onChange={(e) => setRayon(e.target.value)}
                className="w-24 rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
              />
            </div>
          </div>
          {/* Enregistrer la zone */}
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <label className="mb-1 block text-xs text-[var(--muted)]">
                Enregistrer cette zone (nom)
              </label>
              <input
                value={nomZone}
                onChange={(e) => setNomZone(e.target.value)}
                placeholder="ex : ZA Wambrechies"
                className="w-full rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm"
              />
            </div>
            <button
              type="button"
              onClick={enregistrerZone}
              disabled={pending || !adresse.trim() || !nomZone.trim()}
              className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm font-medium hover:bg-slate-50 disabled:opacity-40"
            >
              💾 Enregistrer
            </button>
          </div>
          {zones.length > 0 && (
            <ul className="flex flex-wrap gap-1.5">
              {zones.map((z) => (
                <li
                  key={z.id}
                  className="flex items-center gap-1 rounded-full border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--muted)]"
                >
                  {z.nom}
                  <button
                    type="button"
                    onClick={() => supprimerZone(z.id)}
                    className="text-[var(--muted)] hover:text-red-600"
                    aria-label={`Supprimer ${z.nom}`}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div>
        <label className="mb-1 block text-sm font-medium">Taille des entreprises</label>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {EFFECTIF_PRESETS.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setEffectifPreset(p.id)}
              title={p.hint}
              className={`rounded-lg border px-2.5 py-1.5 text-sm font-medium transition ${
                effectifPreset === p.id
                  ? "border-[var(--brand)] bg-[var(--brand)] text-white"
                  : "border-[var(--border)] text-[var(--muted)] hover:bg-slate-50"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        {effectifPreset === "custom" ? (
          <div className="mt-2 flex items-end gap-2">
            <div>
              <label className="mb-1 block text-xs text-[var(--muted)]">Min. (salariés)</label>
              <input
                type="number"
                min={0}
                value={effectifMinCustom}
                onChange={(e) => setEffectifMinCustom(e.target.value)}
                placeholder="10"
                className="w-28 rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
              />
            </div>
            <span className="pb-2 text-[var(--muted)]">–</span>
            <div>
              <label className="mb-1 block text-xs text-[var(--muted)]">Max. (salariés)</label>
              <input
                type="number"
                min={0}
                value={effectifMaxCustom}
                onChange={(e) => setEffectifMaxCustom(e.target.value)}
                placeholder="250"
                className="w-28 rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
              />
            </div>
          </div>
        ) : (
          <p className="mt-1 text-xs text-[var(--muted)]">{preset.hint}</p>
        )}
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium">Volume cible</label>
        <div className="flex gap-2">
          <input
            type="number"
            min={1}
            value={volume}
            onChange={(e) => setVolume(e.target.value)}
            className="w-32 rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
          />
          <div className="flex gap-1">
            {VOLUME_PRESETS.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setVolume(String(p))}
                className={`rounded-lg border px-2.5 py-1.5 text-xs font-medium transition ${
                  volume === String(p)
                    ? "border-[var(--brand)] bg-[var(--brand)] text-white"
                    : "border-[var(--border)] text-[var(--muted)] hover:bg-slate-50"
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>
        <p className="mt-1 text-xs text-[var(--muted)]">
          Le moteur s&apos;arrête au volume atteint ou au budget plafond, au
          premier des deux.
        </p>
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium">
          Budget plafond (€)
        </label>
        <input
          type="number"
          value={budget}
          onChange={(e) => setBudget(e.target.value)}
          className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
        />
        {!isTest && volumeNum > 0 && (
          <p
            className={`mt-1 text-xs ${
              budgetInsuffisant ? "text-amber-700" : "text-[var(--muted)]"
            }`}
          >
            Coût estimé pour {volumeNum} leads :{" "}
            <span className="font-medium">
              {formatEur(estimation.bas)}–{formatEur(estimation.haut)}
            </span>{" "}
            <span className="text-[var(--muted)]">
              (Places + Claude ; haut = avec enrichissement Dropcontact)
            </span>
            {budgetInsuffisant && (
              <>
                {" "}
                — ⚠️ budget plafond ({formatEur(budgetNum)}) sous l&apos;estimé
                basse : le run pourrait s&apos;arrêter avant le volume visé.
              </>
            )}
          </p>
        )}
      </div>

      <label className="flex items-start gap-2 rounded-lg border border-[var(--border)] bg-slate-50 p-3 text-sm">
        <input
          type="checkbox"
          checked={isTest}
          onChange={(e) => setIsTest(e.target.checked)}
          className="mt-0.5"
        />
        <span>
          <span className="font-medium">Recherche test (mode démo, gratuit)</span>
          <span className="block text-xs text-[var(--muted)]">
            Génère de faux prospects sans appel externe ni coût — pour essayer
            l&apos;interface.
          </span>
        </span>
      </label>

      <button
        type="submit"
        disabled={pending || !verticaleId}
        className={`w-full rounded-lg py-2.5 text-sm font-semibold text-white disabled:opacity-50 ${
          isTest
            ? "bg-violet-600 hover:bg-violet-700"
            : "bg-[var(--brand)] hover:bg-[var(--brand-dark)]"
        }`}
      >
        {pending
          ? "Envoi…"
          : isTest
            ? "Vérifier la recherche test"
            : "Vérifier la recherche"}
      </button>
      {msg && <p className="text-sm">{msg}</p>}
    </form>

      {/* Modale de validation « Voilà ce que tu vas lancer » (garde-fou agent-first :
          on récapitule, on alerte si le ciblage déborde, l'utilisateur confirme). */}
      {confirmOpen && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 backdrop-blur-sm sm:items-center"
          onClick={() => setConfirmOpen(false)}
        >
          <div
            className="my-auto w-full max-w-md rounded-2xl border border-[var(--border)] bg-white shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="rounded-t-2xl bg-gradient-to-br from-[var(--brand)]/10 to-transparent px-6 pb-4 pt-5">
              <h2 className="text-lg font-bold">
                {isTest ? "Vérifier la recherche test" : "Vérifier la recherche"}
              </h2>
              <p className="mt-0.5 text-sm text-[var(--muted)]">
                Voilà ce que tu vas lancer — confirme ou reviens ajuster.
              </p>
            </div>

            <div className="space-y-3 px-6 py-4 text-sm">
              <dl className="space-y-1.5">
                <div className="flex justify-between gap-3">
                  <dt className="text-[var(--muted)]">Cible</dt>
                  <dd className="text-right font-medium">{cibleNom}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-[var(--muted)]">Périmètre</dt>
                  <dd className="text-right font-medium">
                    {mode === "departement"
                      ? `Département ${departement || "—"}`
                      : `${adresse || "—"} · ${Number(rayon) || 10} km`}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-[var(--muted)]">Effectif</dt>
                  <dd className="text-right font-medium">
                    {effectifLabel(effMin, effMax)}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-[var(--muted)]">Volume visé</dt>
                  <dd className="text-right font-medium">{volumeNum || "—"} leads</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-[var(--muted)]">Budget plafond</dt>
                  <dd className="text-right font-medium">
                    {isTest
                      ? "Gratuit (mode démo)"
                      : `${formatEur(budgetNum)} · est. ${formatEur(estimation.bas)}–${formatEur(estimation.haut)}`}
                  </dd>
                </div>
              </dl>

              {verdict.alertes.length > 0 && (
                <ul className="space-y-1.5">
                  {verdict.alertes.map((a, i) => (
                    <li
                      key={i}
                      className="flex gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"
                    >
                      <span aria-hidden>⚠️</span>
                      <span>{a}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 rounded-b-2xl border-t border-[var(--border)] bg-slate-50 px-6 py-3">
              <button
                type="button"
                onClick={() => setConfirmOpen(false)}
                className="rounded-lg border border-[var(--border)] bg-white px-4 py-1.5 text-sm font-medium hover:bg-slate-50"
              >
                Modifier
              </button>
              <button
                type="button"
                onClick={confirmer}
                disabled={pending}
                className={`rounded-lg px-4 py-1.5 text-sm font-semibold text-white disabled:opacity-50 ${
                  isTest
                    ? "bg-violet-600 hover:bg-violet-700"
                    : "bg-[var(--brand)] hover:bg-[var(--brand-dark)]"
                }`}
              >
                {pending ? "Envoi…" : "Confirmer le lancement"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
