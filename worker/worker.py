"""Boucle de traitement des runs."""

from __future__ import annotations

import logging
import os
from typing import Any

from .config import WorkerConfig
from .pipeline import Pipeline, RunContext, build_pipeline
from .supabase_rest import SupabaseRest

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

    def _heartbeat(self, *, pending: int | None = None, last_error: str | None = None) -> None:
        """Écrit le battement de cœur (non bloquant : ne doit jamais tuer la boucle)."""
        try:
            self.db.heartbeat(
                mode=self.config.mode,
                version=self.config.version,
                pending=pending,
                last_error=last_error,
                keys=self._keys_presence(),
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
        try:
            verticale = self.db.get_verticale(run.get("verticale_id"))
            ctx = RunContext(
                run=run,
                verticale=verticale,
                max_leads=self.config.max_leads,
                max_budget_eur=self.config.max_budget_eur,
            )

            def emit(etape: str, progress: int, counts: dict[str, int]) -> None:
                self.db.update_run_progress(
                    run_id, etape=etape, progress=progress, counts=counts
                )

            result = self._pipeline_for(run).run(ctx, emit)
            self.db.insert_leads(result.leads)
            self.db.finalize_run(
                run_id,
                status="termine",
                counts=result.counts,
                cout_eur=result.cout_eur,
            )
            logger.info(
                "Run %s : terminé — %d leads, %.2f €",
                run_id,
                len(result.leads),
                result.cout_eur,
            )
        except Exception as exc:  # noqa: BLE001 — on veut capturer pour marquer le run échoué
            logger.exception("Run %s : échec", run_id)
            # Remonte aussi l'erreur au heartbeat → visible dans l'UI sans logs Railway.
            self._heartbeat(last_error=str(exc)[:500])
            try:
                self.db.finalize_run(
                    run_id, status="echoue", counts={}, cout_eur=0.0, erreur=str(exc)[:500]
                )
            except Exception:  # noqa: BLE001
                logger.exception("Run %s : impossible de marquer l'échec", run_id)
