"""Boucle de traitement des runs."""

from __future__ import annotations

import logging
import os
from typing import Any

from .config import WorkerConfig
from .pipeline import Pipeline, RunContext, build_pipeline, raison_degradation
from .supabase_rest import SupabaseRest

# Colonnes de `runs` écrites par le worker — vérifiées au préflight (dérive de
# schéma = runs qui bouclent en silence, cf. bug cout_detail).
_COLONNES_RUNS_REQUISES = ["status", "counts", "cout_eur", "cout_detail", "erreur", "qualite"]

logger = logging.getLogger("renoboost.worker")


class Worker:
    def __init__(
        self,
        config: WorkerConfig,
        db: SupabaseRest | None = None,
        pipeline: Pipeline | None = None,
        demo_pipeline: Pipeline | None = None,
    ) -> None:
        self.config = config
        self.db = db or SupabaseRest(
            config.rest_url, config.service_role_key, config.request_timeout_s
        )
        self.pipeline = pipeline or build_pipeline(config.mode)
        # Pipeline utilisé pour les runs marqués « test » : mode démo (faux leads,
        # zéro appel externe), quel que soit WORKER_MODE.
        self._demo_pipeline = demo_pipeline

    def _pipeline_for(self, run: dict[str, Any]) -> Pipeline:
        """Choisit le pipeline d'un run : démo si `is_test`, sinon le pipeline configuré."""
        if run.get("is_test"):
            return self._demo_pipeline or build_pipeline("demo")
        return self.pipeline

    @staticmethod
    def _keys_presence() -> dict[str, bool]:
        """Présence (jamais la valeur) des clés API du mode real, pour l'UI.

        Lue directement de l'environnement (≈ « la clé est-elle posée sur
        Railway ») sans instancier la config cœur, qui échouerait si une clé
        requise manque.
        """
        return {
            name: bool(os.environ.get(env, "").strip())
            for name, env in (
                ("google_places", "GOOGLE_PLACES_API_KEY"),
                ("anthropic", "ANTHROPIC_API_KEY"),
                ("pappers", "PAPPERS_API_KEY"),
                ("dropcontact", "DROPCONTACT_API_KEY"),
            )
        }

    def _heartbeat(
        self,
        *,
        pending: int | None = None,
        last_error: str | None = None,
        clear_error: bool = False,
    ) -> None:
        """Écrit le battement de cœur (non bloquant : ne doit jamais tuer la boucle)."""
        try:
            self.db.heartbeat(
                mode=self.config.mode,
                version=self.config.version,
                pending=pending,
                last_error=last_error,
                keys=self._keys_presence(),
                clear_error=clear_error,
            )
        except Exception:  # noqa: BLE001 — l'observabilité ne doit pas casser le traitement
            logger.warning("Heartbeat échoué (non bloquant).", exc_info=True)

    def heartbeat_tick(self) -> None:
        """Battement de cœur léger, appelé par un thread dédié pour garder le
        `last_seen_at` frais MÊME pendant un run long (la boucle principale est
        bloquée dans process_run pendant ce temps)."""
        self._heartbeat()

    def _reap_stale_runs(self) -> None:
        """Remet en file les runs orphelins (worker mort/redéployé en plein run)."""
        try:
            n = self.db.requeue_stale_runs(self.config.stale_run_timeout_s)
            if n:
                logger.warning("Reaper : %d run(s) orphelin(s) remis en file.", n)
        except Exception:  # noqa: BLE001 — la récupération ne doit pas casser la boucle
            logger.warning("Reaper échoué (non bloquant).", exc_info=True)

    def preflight(self) -> list[str]:
        """Vérifs au démarrage : signaler TÔT une config cassée plutôt que de
        laisser des runs échouer en silence (cf. cout_detail manquant, modèle
        Claude invalide). Non bloquant : on remonte sur la pastille et on continue.
        """
        problemes: list[str] = []

        # 1) Schéma DB : colonnes écrites par le worker présentes ?
        try:
            souci = self.db.verifier_colonnes_runs(_COLONNES_RUNS_REQUISES)
            if souci:
                problemes.append(f"DB : {souci}")
        except Exception as exc:  # noqa: BLE001 — le préflight ne doit jamais tuer le worker
            problemes.append(f"DB injoignable : {exc}")

        # 2) Claude joignable (mode réel) avec le modèle effectivement utilisé.
        if self.config.mode == "real":
            souci = self._verifier_claude()
            if souci:
                problemes.append(f"Claude : {souci}")

        if problemes:
            resume = " | ".join(problemes)
            logger.error("Préflight : %s", resume)
            self._heartbeat(last_error=f"Préflight KO — {resume}")
        else:
            logger.info("Préflight OK.")
        return problemes

    @staticmethod
    def _verifier_claude() -> str | None:
        """Ping minimal de l'API Claude (1 token) avec le modèle L4 par défaut,
        résolu en identifiant d'API exact. Détecte clé/modèle invalides au boot."""
        key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not key:
            return "ANTHROPIC_API_KEY absente."
        try:
            from anthropic import Anthropic

            from renoboost_leads.common.anthropic_models import resolve_model_id
            from renoboost_leads.stage4_prospection.client import ClaudeClientConfig

            modele = resolve_model_id(ClaudeClientConfig.modele)
            Anthropic(api_key=key).messages.create(
                model=modele,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            return None
        except Exception as exc:  # noqa: BLE001
            return f"{type(exc).__name__}: {str(exc)[:160]}"

    def poll_once(self) -> int:
        """Traite les runs en attente. Renvoie le nombre de runs traités."""
        # Récupère d'abord les runs orphelins (les remet en `demande`) pour
        # qu'ils soient repris au même tour.
        self._reap_stale_runs()
        pending = self.db.fetch_pending_runs(limit=5)
        # Battement de cœur à chaque tour (y compris à vide) → l'UI sait que le
        # process tourne et combien de runs attendent.
        self._heartbeat(pending=len(pending))
        traites = 0
        for run in pending:
            claimed = self.db.claim_run(run["id"])
            if claimed is None:
                # Un autre worker l'a pris entre-temps.
                continue
            self.process_run(claimed)
            traites += 1
        return traites

    def process_run(self, run: dict[str, Any]) -> None:
        run_id = run["id"]
        logger.info("Run %s : démarrage", run_id)
        # Suit la dernière étape atteinte → on sait OÙ ça a coincé en cas d'échec.
        etape_courante = {"nom": "Initialisation"}
        try:
            # Auto-check AVANT de lancer (mode réel) : si une dépendance critique
            # est KO (clé/modèle/crédits Claude), on échoue tout de suite avec un
            # diagnostic clair, SANS engager de budget (Places/Dropcontact).
            if self.config.mode == "real":
                souci = self._verifier_claude()
                if souci:
                    msg = (
                        f"Recherche non lancée — pré-vérification échouée à l'étape "
                        f"« Scoring (Claude) » : {souci}. Aucun budget engagé."
                    )
                    logger.error("Run %s : %s", run_id, msg)
                    self.db.finalize_run(
                        run_id, status="echoue", counts={}, cout_eur=0.0, erreur=msg
                    )
                    self._heartbeat(last_error=msg)
                    return

            verticale = self.db.get_verticale(run.get("verticale_id"))
            ctx = RunContext(
                run=run,
                verticale=verticale,
                max_leads=self.config.max_leads,
                max_budget_eur=self.config.max_budget_eur,
            )

            def emit(etape: str, progress: int, counts: dict[str, int]) -> None:
                etape_courante["nom"] = etape
                self.db.update_run_progress(
                    run_id, etape=etape, progress=progress, counts=counts
                )

            result = self._pipeline_for(run).run(ctx, emit)
            self.db.insert_leads(result.leads)
            # Garde-fou anti-dégradation silencieuse : un run techniquement
            # « terminé » mais anormalement pauvre (0 découverte / 0 lead / scoring
            # KO) porte un diagnostic visible (champ erreur), au lieu d'un faux
            # succès vert. Le statut reste « termine » (les leads restent exploitables).
            degradation = raison_degradation(result.counts)
            self.db.finalize_run(
                run_id,
                status="termine",
                counts=result.counts,
                cout_eur=result.cout_eur,
                cout_detail=result.cout_detail,
                erreur=(f"Recherche dégradée : {degradation}" if degradation else None),
            )
            logger.info(
                "Run %s : terminé — %d leads, %.2f €%s",
                run_id,
                len(result.leads),
                result.cout_eur,
                f" [DÉGRADÉ : {degradation}]" if degradation else "",
            )
            if degradation:
                # Remonte sur la pastille worker : visible sans fouiller les runs.
                self._heartbeat(last_error=f"Run dégradé : {degradation}")
            else:
                # Run sain → efface le dernier échec affiché (sinon il resterait collé).
                self._heartbeat(clear_error=True)
        except Exception as exc:  # noqa: BLE001 — on veut capturer pour marquer le run échoué
            logger.exception("Run %s : échec", run_id)
            # Diagnostic « où ça a coincé » : étape atteinte + cause.
            diag = f"Bloqué à l'étape « {etape_courante['nom']} » : {str(exc)[:400]}"
            self._heartbeat(last_error=diag[:500])
            try:
                self.db.finalize_run(
                    run_id, status="echoue", counts={}, cout_eur=0.0, erreur=diag[:500]
                )
            except Exception:  # noqa: BLE001
                logger.exception("Run %s : impossible de marquer l'échec", run_id)
