"""Outils agent ciblés : enrichissement L3.5 et scoring L4 sur session existante.

Pattern identique à `pipeline.run_pipeline` : subprocess sur `cli run` pour
éviter d'importer toute la machinerie métier (Anthropic, Dropcontact) dans le
processus de l'agent. Différence : on cible une **session existante** (les
CSV L1+L2+L3 sont déjà là) et on lance UN seul étage supplémentaire.

Stats post-run extraites du CSV produit pour donner au modèle un retour
exploitable (taux email vérifié, top leads, coût...) sans qu'il ait à
relancer `read_session` derrière.
"""

from __future__ import annotations

import csv
import shlex
import subprocess
import sys
from pathlib import Path

from ...settings import PROJECT_ROOT
from .sessions import OUTPUT_ROOT


def _tail(s: str, n: int) -> str:
    if not s:
        return ""
    return "\n".join(s.splitlines()[-n:])


def _lire_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _pct(num: int, den: int) -> float:
    return round(100.0 * num / den, 1) if den else 0.0


def _stats_l3_5_csv(rows: list[dict]) -> dict:
    """Stats lisibles à partir d'`etage3_5_enrichissement.csv`."""
    n = len(rows)
    if not n:
        return {"total": 0}
    avec_email = sum(1 for r in rows if (r.get("email_dropcontact") or "").strip())
    correct = sum(
        1
        for r in rows
        if (r.get("qualification_email_dropcontact") or "").strip().lower() == "correct"
    )
    avec_tel = sum(
        1 for r in rows if (r.get("telephone_direct_dropcontact") or "").strip()
    )
    avec_linkedin = sum(
        1
        for r in rows
        if (r.get("linkedin_dirigeant_dropcontact") or "").strip()
        or (r.get("linkedin_entreprise_dropcontact") or "").strip()
    )
    enrichis = sum(1 for r in rows if (r.get("enrichi_dropcontact") or "") == "VRAI")
    return {
        "total": n,
        "enrichis": enrichis,
        "pct_email_dropcontact": _pct(avec_email, n),
        "pct_email_correct": _pct(correct, n),
        "pct_tel_direct": _pct(avec_tel, n),
        "pct_linkedin": _pct(avec_linkedin, n),
    }


def _stats_l4_csv(rows: list[dict], seuil_top: int = 70) -> dict:
    """Stats lisibles à partir d'`etage4_prospection.csv`."""
    n = len(rows)
    if not n:
        return {"total": 0}
    scores: list[int] = []
    for r in rows:
        try:
            v = int(float(r.get("score_interet") or 0))
        except (TypeError, ValueError):
            continue
        scores.append(v)
    top = sum(1 for r in rows if (r.get("top_lead") or "") == "VRAI")
    avec_pitch = sum(1 for r in rows if (r.get("pitch_propose") or "").strip())
    score_moyen = round(sum(scores) / len(scores), 1) if scores else 0.0
    score_median = sorted(scores)[len(scores) // 2] if scores else 0
    return {
        "total": n,
        "top_leads": top,
        "pct_top_leads": _pct(top, n),
        "score_moyen": score_moyen,
        "score_median": score_median,
        "pct_avec_pitch": _pct(avec_pitch, n),
        "seuil_top": seuil_top,
    }


def _executer_etage_sur_session(
    session_id: str,
    stage: str,
    csv_attendu: str,
    fonction_stats,
    dry_run: bool,
    timeout_s: int,
) -> dict:
    """Factorisation : lance `cli run --from-csv --stages <stage>` puis stats."""
    dossier = OUTPUT_ROOT / session_id
    if not dossier.is_dir():
        return {"error": f"session inconnue : '{session_id}'"}

    csv_l3 = dossier / "etage3_contacts.csv"
    if not csv_l3.exists():
        return {
            "error": "etage3_contacts.csv absent — lance L1+L2+L3 avant.",
            "session_id": session_id,
        }

    cfg = dossier / "config_snapshot.yaml"
    if not cfg.exists():
        return {
            "error": (
                "config_snapshot.yaml absent dans la session — impossible de "
                "récupérer les paramètres. Utilise plutôt run_pipeline avec "
                "le YAML original."
            ),
            "session_id": session_id,
        }

    csv_l1 = dossier / "etage1_decouverte.csv"
    if not csv_l1.exists():
        return {
            "error": "etage1_decouverte.csv absent (session incomplète).",
            "session_id": session_id,
        }

    cmd = [
        sys.executable,
        "-m",
        "renoboost_leads.cli",
        "run",
        "--config",
        str(cfg),
        "--stages",
        stage,
        "--from-csv",
        str(csv_l1),
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
            "session_id": session_id,
        }

    stats: dict = {}
    csv_out = dossier / csv_attendu
    csv_path_str: str | None = None
    if csv_out.exists():
        stats = fonction_stats(_lire_csv(csv_out))
        try:
            csv_path_str = str(csv_out.relative_to(PROJECT_ROOT))
        except ValueError:
            csv_path_str = str(csv_out)

    return {
        "session_id": session_id,
        "stage": stage,
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "dry_run": dry_run,
        "csv_path": csv_path_str,
        "stats": stats,
        "stdout_tail": _tail(proc.stdout, 40),
        "stderr_tail": _tail(proc.stderr, 20),
        "command": shlex.join(cmd),
    }


def enrich_l3_5_on_session(
    session_id: str,
    dry_run: bool = False,
    timeout_s: int = 1800,
) -> dict:
    """Lance l'étage L3.5 (enrichissement Dropcontact) sur une session L3 existante.

    Prérequis : `etage3_contacts.csv` + `config_snapshot.yaml` présents.
    Produit : `etage3_5_enrichissement.csv` + stats (% email Dropcontact,
    % email qualif `correct`, % tel direct, % LinkedIn).
    """
    return _executer_etage_sur_session(
        session_id=session_id,
        stage="3.5",
        csv_attendu="etage3_5_enrichissement.csv",
        fonction_stats=_stats_l3_5_csv,
        dry_run=dry_run,
        timeout_s=timeout_s,
    )


def score_l4_on_session(
    session_id: str,
    dry_run: bool = False,
    timeout_s: int = 1800,
) -> dict:
    """Lance l'étage L4 (scoring Claude + pitch) sur une session existante.

    Le CLI source automatiquement la version la plus riche : L3.5 si présent,
    sinon L3. Produit `etage4_prospection.csv` + stats (top_leads, score moyen,
    score médian, % avec pitch).
    """
    return _executer_etage_sur_session(
        session_id=session_id,
        stage="4",
        csv_attendu="etage4_prospection.csv",
        fonction_stats=_stats_l4_csv,
        dry_run=dry_run,
        timeout_s=timeout_s,
    )


SCHEMAS = [
    {
        "name": "enrich_l3_5_on_session",
        "description": (
            "Lance l'étage 3.5 (enrichissement Dropcontact : email vérifié, "
            "tél direct, LinkedIn, civilité) sur une session existante "
            "ayant déjà L3. Filtre intelligent : ne traite que les leads "
            "passant les filtres entreprise. Coût indicatif : ~0.10€/lead "
            "éligible. Préfère dry_run=true pour valider sans facturer. "
            "Retourne stats post-run (% email, % tel, % LinkedIn)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": (
                        "Identifiant de la session (dossier sous data/output/). "
                        "L3 et config_snapshot.yaml doivent y être présents."
                    ),
                },
                "dry_run": {
                    "type": "boolean",
                    "description": (
                        "Si true, utilise le simulateur Dropcontact (aucun "
                        "appel API, aucun coût)."
                    ),
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
            "required": ["session_id"],
        },
    },
    {
        "name": "score_l4_on_session",
        "description": (
            "Lance l'étage 4 (scoring qualitatif Claude + génération de "
            "pitch) sur une session existante. Source automatique : L3.5 "
            "prioritaire, fallback L3. Coût indicatif : ~0.02€/lead. "
            "Retourne stats post-run (top_leads, score moyen/médian, % pitch). "
            "Préfère dry_run=true pour tester sans appeler Anthropic."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": (
                        "Identifiant de la session. L3 (et idéalement L3.5) "
                        "et config_snapshot.yaml doivent y être présents."
                    ),
                },
                "dry_run": {
                    "type": "boolean",
                    "description": (
                        "Si true, utilise le simulateur Claude (aucun appel "
                        "Anthropic, aucun coût). Scores synthétiques."
                    ),
                    "default": False,
                },
                "timeout_s": {
                    "type": "integer",
                    "description": "Timeout en secondes (défaut 1800).",
                    "default": 1800,
                    "minimum": 30,
                    "maximum": 7200,
                },
            },
            "required": ["session_id"],
        },
    },
]

DISPATCH = {
    "enrich_l3_5_on_session": enrich_l3_5_on_session,
    "score_l4_on_session": score_l4_on_session,
}
