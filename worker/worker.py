"""Boucle de traitement des runs."""

from __future__ import annotations

import logging
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
    ) -> None:
        self.config = config
        self.db = db or SupabaseRest(
            config.rest_url, config.service_role_key, config.request_timeout_s
        )
        self.pipeline = pipeline or build_pipeline(config.mode)

    def poll_once(self) -> int:
        """Traite les runs en attente. Renvoie le nombre de runs traités."""
        pending = self.db.fetch_pending_runs(limit=5)
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
            ctx = RunContext(run=run, verticale=verticale, max_leads=self.config.max_leads)

            def emit(etape: str, progress: int, counts: dict[str, int]) -> None:
                self.db.update_run_progress(
                    run_id, etape=etape, progress=progress, counts=counts
                )

            result = self.pipeline.run(ctx, emit)
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
            try:
                self.db.finalize_run(
                    run_id, status="echoue", counts={}, cout_eur=0.0, erreur=str(exc)[:500]
                )
            except Exception:  # noqa: BLE001
                logger.exception("Run %s : impossible de marquer l'échec", run_id)
