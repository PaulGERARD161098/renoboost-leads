"""Point d'entrée : `python -m worker`.

Boucle indéfiniment, poll les runs toutes les `WORKER_POLL_INTERVAL_S` secondes,
et s'arrête proprement sur SIGINT/SIGTERM (redéploiements Railway).
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time
from types import FrameType

from .config import ConfigError, WorkerConfig
from .worker import Worker


def _setup_logging() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )


def main() -> int:
    _setup_logging()
    log = logging.getLogger("renoboost.worker")

    try:
        config = WorkerConfig.from_env()
    except ConfigError as exc:
        log.error("Configuration invalide : %s", exc)
        return 2

    worker = Worker(config)
    log.info(
        "Worker démarré (mode=%s, intervalle=%.0fs). En attente de runs…",
        config.mode,
        config.poll_interval_s,
    )

    running = {"on": True}

    def _stop(signum: int, _frame: FrameType | None) -> None:
        log.info("Signal %s reçu — arrêt après le run courant.", signum)
        running["on"] = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    # Thread de heartbeat : garde `last_seen_at` frais MÊME pendant un run long
    # (la boucle principale est bloquée dans process_run pendant ce temps, donc
    # sans ce thread la pastille « Worker » paraîtrait à tort silencieuse).
    def _heartbeat_loop() -> None:
        while running["on"]:
            worker.heartbeat_tick()
            time.sleep(config.poll_interval_s)

    threading.Thread(target=_heartbeat_loop, name="heartbeat", daemon=True).start()

    while running["on"]:
        try:
            traites = worker.poll_once()
        except Exception:  # noqa: BLE001 — la boucle ne doit jamais mourir sur une erreur réseau
            log.exception("Erreur pendant le poll — nouvelle tentative après pause.")
            traites = 0
        # Si on a traité des runs, on enchaîne sans attendre (file peut-être pleine).
        if not traites:
            time.sleep(config.poll_interval_s)

    log.info("Worker arrêté proprement.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
