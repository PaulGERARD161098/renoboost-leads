"""Outil `run_pipeline` — wrap subprocess de `python -m renoboost_leads.cli run`.

On évite d'importer la machinerie interne du CLI (gros graphe d'imports,
risque d'effet de bord). Subprocess avec timeout + capture stdout/stderr.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

from ...settings import PROJECT_ROOT

ETAGES_VALIDES = {"1", "2", "3", "3.5", "4"}


def run_pipeline(
    config_path: str,
    stages: str = "1,2,3",
    dry_run: bool = False,
    timeout_s: int = 1800,
) -> dict:
    """Lance un run en subprocess. Bloquant.

    `config_path` relatif au repo OK. `stages` = CSV ('1,2,3' ou '3.5,4').
    Renvoie returncode + stdout (queue) + stderr (queue) + commande exécutée.
    """
    cfg = Path(config_path)
    if not cfg.is_absolute():
        cfg = PROJECT_ROOT / cfg
    if not cfg.exists():
        return {"error": f"config introuvable : {cfg}"}

    demandes = [s.strip() for s in stages.split(",") if s.strip()]
    invalides = [s for s in demandes if s not in ETAGES_VALIDES]
    if invalides:
        return {
            "error": f"étages invalides : {invalides}. Valides : {sorted(ETAGES_VALIDES)}"
        }
    if not demandes:
        return {"error": "aucun étage demandé"}

    cmd = [
        sys.executable,
        "-m",
        "renoboost_leads.cli",
        "run",
        "--config",
        str(cfg),
        "--stages",
        ",".join(demandes),
    ]
    if dry_run:
        cmd.append("--dry-run")

    try:
        proc = subprocess.run(  # noqa: S603 — argv list, pas de shell
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "error": f"timeout après {timeout_s}s",
            "command": shlex.join(cmd),
        }

    return {
        "returncode": proc.returncode,
        "stdout_tail": _tail(proc.stdout, n=80),
        "stderr_tail": _tail(proc.stderr, n=40),
        "command": shlex.join(cmd),
        "ok": proc.returncode == 0,
    }


def _tail(s: str, n: int) -> str:
    if not s:
        return ""
    lignes = s.splitlines()
    return "\n".join(lignes[-n:])


SCHEMAS = [
    {
        "name": "run_pipeline",
        "description": (
            "Lance un run de prospection RénoBoost en subprocess. Bloquant — "
            "renvoie returncode + dernières lignes stdout/stderr quand fini. "
            "Coût indicatif : L1 ~0.30€/30 leads, L2 gratuit, L3 ~0.20€, "
            "L3.5 ~0.10€/lead, L4 ~0.02€/lead. Préfère dry_run=true pour tester."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "config_path": {
                    "type": "string",
                    "description": (
                        "Chemin du YAML (relatif repo OK, "
                        "ex 'config/pilote_phase1.yaml')."
                    ),
                },
                "stages": {
                    "type": "string",
                    "description": "CSV d'étages : '1,2,3' ou '3.5,4'. Valides : 1, 2, 3, 3.5, 4.",
                    "default": "1,2,3",
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Si true, aucun appel API payant.",
                    "default": False,
                },
                "timeout_s": {
                    "type": "integer",
                    "description": "Timeout en secondes (défaut 1800 = 30 min).",
                    "default": 1800,
                    "minimum": 30,
                    "maximum": 7200,
                },
            },
            "required": ["config_path"],
        },
    }
]

DISPATCH = {"run_pipeline": run_pipeline}
