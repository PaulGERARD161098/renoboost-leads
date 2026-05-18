"""Outils sessions : `list_sessions`, `read_session`.

Inspecte `data/output/<session_id>/` :
- etage1_decouverte.csv
- etage2_entreprises.csv
- etage3_contacts.csv (+ etage3_contacts_hors_filtre.csv)
- etage3_5_enrichment.csv
- etage4_prospection.csv
- run_stats.json
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from ...settings import PROJECT_ROOT

OUTPUT_ROOT = PROJECT_ROOT / "data" / "output"

STAGE_FILES = {
    "1": "etage1_decouverte.csv",
    "2": "etage2_entreprises.csv",
    "3": "etage3_contacts.csv",
    "3_hors_filtre": "etage3_contacts_hors_filtre.csv",
    "3.5": "etage3_5_enrichment.csv",
    "4": "etage4_prospection.csv",
}


def _scan_sessions() -> list[Path]:
    if not OUTPUT_ROOT.exists():
        return []
    return sorted(
        [d for d in OUTPUT_ROOT.iterdir() if d.is_dir()],
        key=lambda p: p.name,
        reverse=True,
    )


def list_sessions(limit: int = 20) -> dict:
    """Liste les sessions, plus récentes d'abord."""
    sessions = _scan_sessions()[: max(1, int(limit))]
    items = []
    for d in sessions:
        stats_path = d / "run_stats.json"
        meta = {"session_id": d.name, "stages_disponibles": []}
        for stage_key, fname in STAGE_FILES.items():
            if (d / fname).exists():
                meta["stages_disponibles"].append(stage_key)
        if stats_path.exists():
            try:
                raw = json.loads(stats_path.read_text(encoding="utf-8"))
                meta["campaign"] = raw.get("campaign")
                meta["debut"] = raw.get("debut")
                meta["fin"] = raw.get("fin")
            except json.JSONDecodeError:
                pass
        items.append(meta)
    return {"count": len(items), "sessions": items}


def _row_count_csv(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as f:
        return max(0, sum(1 for _ in f) - 1)


def _sample_csv(path: Path, n: int = 5) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [row for _, row in zip(range(n), reader, strict=False)]


def read_session(session_id: str, stage: str = "3", sample_size: int = 5) -> dict:
    """Stats + N premiers leads d'un étage d'une session."""
    if stage not in STAGE_FILES:
        return {
            "error": f"stage inconnu : '{stage}'. Valides : {list(STAGE_FILES.keys())}"
        }
    dossier = OUTPUT_ROOT / session_id
    if not dossier.is_dir():
        return {"error": f"session inconnue : '{session_id}'"}
    fichier = dossier / STAGE_FILES[stage]
    if not fichier.exists():
        return {
            "session_id": session_id,
            "stage": stage,
            "exists": False,
            "message": f"Étage {stage} pas encore lancé pour cette session.",
        }
    try:
        file_str = str(fichier.relative_to(PROJECT_ROOT))
    except ValueError:
        file_str = str(fichier)
    return {
        "session_id": session_id,
        "stage": stage,
        "exists": True,
        "file": file_str,
        "row_count": _row_count_csv(fichier),
        "sample": _sample_csv(fichier, n=max(0, int(sample_size))),
        "consulted_at": datetime.now(timezone.utc).isoformat(),
    }


SCHEMAS = [
    {
        "name": "list_sessions",
        "description": (
            "Liste les sessions de prospection présentes dans `data/output/`, "
            "plus récentes d'abord. Renvoie l'id, la campagne, les dates "
            "début/fin, et les étages disponibles (1, 2, 3, 3_hors_filtre, "
            "3.5, 4)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Nombre max de sessions à renvoyer (défaut 20).",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                }
            },
        },
    },
    {
        "name": "read_session",
        "description": (
            "Lit les stats et N premiers leads d'un étage d'une session. "
            "Utilise list_sessions d'abord pour connaître les session_id "
            "et les étages disponibles."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Identifiant de session (ex: 20260518-091234-pilote59).",
                },
                "stage": {
                    "type": "string",
                    "enum": list(STAGE_FILES.keys()),
                    "description": "Étage à lire.",
                    "default": "3",
                },
                "sample_size": {
                    "type": "integer",
                    "description": "Nombre de lignes échantillon (défaut 5, max 20).",
                    "default": 5,
                    "minimum": 0,
                    "maximum": 20,
                },
            },
            "required": ["session_id"],
        },
    },
]

DISPATCH = {
    "list_sessions": list_sessions,
    "read_session": read_session,
}
