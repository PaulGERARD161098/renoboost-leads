"""Logger JSON structuré multi-niveaux.

Émet :
- vers stdout : format texte humain (couleurs si TTY, sinon plain)
- vers fichier `<output_dir>/session.log` : format JSON multi-lignes
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.logging import RichHandler


class JSONFileHandler(logging.FileHandler):
    """Émet une ligne JSON par log."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            log_entry: dict[str, Any] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }
            # Champs supplémentaires (passés via extra={})
            for key, value in record.__dict__.items():
                if key not in {
                    "name", "msg", "args", "levelname", "levelno", "pathname",
                    "filename", "module", "exc_info", "exc_text", "stack_info",
                    "lineno", "funcName", "created", "msecs", "relativeCreated",
                    "thread", "threadName", "processName", "process", "message",
                    "taskName", "asctime",
                }:
                    log_entry[key] = value
            if record.exc_info:
                log_entry["exception"] = self.format(record).split("\n", 1)[-1]
            self.stream.write(json.dumps(log_entry, ensure_ascii=False, default=str) + "\n")
            self.flush()
        except Exception:  # noqa: BLE001 — on ne casse jamais sur un log
            self.handleError(record)


_LOGGER_CONFIGURED = False


def setup_logger(
    name: str = "renoboost_leads",
    output_dir: Path | None = None,
    level: str = "INFO",
) -> logging.Logger:
    """Configure le logger global. Idempotent."""
    global _LOGGER_CONFIGURED
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if _LOGGER_CONFIGURED and not output_dir:
        return logger

    # Nettoie les handlers précédents (pour les tests / appels multiples)
    logger.handlers.clear()

    # Handler stdout
    console = Console(file=sys.stderr, force_terminal=sys.stderr.isatty())
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        markup=True,
        rich_tracebacks=True,
    )
    rich_handler.setLevel(level)
    logger.addHandler(rich_handler)

    # Handler fichier JSON
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        file_handler = JSONFileHandler(output_dir / "session.log", encoding="utf-8")
        file_handler.setLevel("DEBUG")
        logger.addHandler(file_handler)

    _LOGGER_CONFIGURED = True
    return logger


def get_logger(name: str = "renoboost_leads") -> logging.Logger:
    """Récupère un logger nommé (pour sous-modules)."""
    return logging.getLogger(name)
