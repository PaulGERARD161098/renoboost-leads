"""Outils `clone_config` et `compare_sessions`.

`clone_config` : duplique un YAML de config existant avec overrides
(zone, secteurs, volume, budget, client_name). Écrit dans
`data/agent/configs/<save_as>.yaml` (zone sandbox, gitignored). Le user
peut le déplacer ensuite dans `config/` s'il veut le versionner. La
config générée est utilisable directement avec `run_pipeline`.

`compare_sessions` : diff de qualité entre 2 sessions. Calcule les
deltas sur SIREN/dirigeant/email + leads_count + duree/coût si dispo.
Utile pour « est-ce que cette zone tape mieux que l'autre ? ».
"""

from __future__ import annotations

import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ...settings import PROJECT_ROOT
from .config import _resolve_config
from .quality import _metriques_l3
from .sessions import OUTPUT_ROOT, STAGE_FILES

GENERATED_ROOT = PROJECT_ROOT / "data" / "agent" / "configs"

# Caractères autorisés dans le nom de fichier généré : lettres, chiffres,
# tirets, underscores, points. Rejette espaces, slashes, autres symboles
# pour éviter toute confusion et collision avec des noms réservés.
_SAVE_AS_RE = re.compile(r"^[\w\-.]+$")

OVERRIDES_AUTORISES = {
    "client_name",
    "zone_codes",
    "zone_type",
    "secteurs",
    "volume_cible",
    "budget_max_eur",
    "rayon_par_point_km",
    "pas_grille_km",
}


def _safe_int(val: Any, name: str) -> tuple[int | None, str | None]:
    """Convertit en int, retourne (valeur, erreur)."""
    try:
        return int(val), None
    except (TypeError, ValueError):
        return None, f"'{name}' doit être un entier, reçu {val!r}"


def _safe_float(val: Any, name: str) -> tuple[float | None, str | None]:
    try:
        return float(val), None
    except (TypeError, ValueError):
        return None, f"'{name}' doit être un nombre, reçu {val!r}"


def _appliquer_overrides(cfg: dict, overrides: dict) -> tuple[dict, list[str]]:
    """Applique les overrides au config parsé, renvoie (cfg modifié, log changes).

    Si une erreur de conversion survient, l'élément correspondant du log
    commence par 'ERREUR : ' — le caller doit vérifier et propager.
    """
    changes = []

    if "client_name" in overrides:
        cfg.setdefault("run", {})
        cfg["run"]["client_name"] = str(overrides["client_name"])
        changes.append(f"run.client_name → {overrides['client_name']}")

    if "zone_codes" in overrides:
        codes = overrides["zone_codes"]
        if isinstance(codes, str):
            codes = [c.strip() for c in codes.split(",") if c.strip()]
        cfg.setdefault("zone", {})
        cfg["zone"]["codes"] = [str(c) for c in codes]
        changes.append(f"zone.codes → {codes}")

    if "zone_type" in overrides:
        cfg.setdefault("zone", {})
        cfg["zone"]["type"] = str(overrides["zone_type"])
        changes.append(f"zone.type → {overrides['zone_type']}")

    if "rayon_par_point_km" in overrides:
        val, err = _safe_int(overrides["rayon_par_point_km"], "rayon_par_point_km")
        if err:
            return cfg, [f"ERREUR : {err}"]
        cfg.setdefault("zone", {})
        cfg["zone"]["rayon_par_point_km"] = val
        changes.append(f"zone.rayon_par_point_km → {val}")

    if "pas_grille_km" in overrides:
        val, err = _safe_int(overrides["pas_grille_km"], "pas_grille_km")
        if err:
            return cfg, [f"ERREUR : {err}"]
        cfg.setdefault("zone", {})
        cfg["zone"]["pas_grille_km"] = val
        changes.append(f"zone.pas_grille_km → {val}")

    if "secteurs" in overrides:
        secteurs = overrides["secteurs"]
        if isinstance(secteurs, list):
            cfg["secteurs"] = [
                {"type": "establishment", "query": s} if isinstance(s, str) else s
                for s in secteurs
            ]
        else:
            return cfg, [f"ERREUR : 'secteurs' doit être une liste, reçu {type(secteurs).__name__}"]
        changes.append(f"secteurs → {len(cfg['secteurs'])} entrées")

    if "volume_cible" in overrides:
        val, err = _safe_int(overrides["volume_cible"], "volume_cible")
        if err:
            return cfg, [f"ERREUR : {err}"]
        cfg.setdefault("volume", {})
        cfg["volume"]["cible"] = val
        changes.append(f"volume.cible → {val}")

    if "budget_max_eur" in overrides:
        val_f, err = _safe_float(overrides["budget_max_eur"], "budget_max_eur")
        if err:
            return cfg, [f"ERREUR : {err}"]
        cfg.setdefault("budget", {})
        cfg["budget"]["max_eur"] = val_f
        changes.append(f"budget.max_eur → {val_f}")

    return cfg, changes


def clone_config(
    source_path: str,
    save_as: str,
    overrides: dict | None = None,
) -> dict[str, Any]:
    """Duplique un config YAML avec overrides. Écrit dans data/agent/configs/.

    Args:
        source_path: chemin du YAML source (sous `config/`, chroot).
        save_as: nom du fichier de sortie (sans extension).
            Écrit dans `data/agent/configs/<save_as>.yaml`.
        overrides: dict avec clés parmi OVERRIDES_AUTORISES (cf. SCHEMAS).

    Returns:
        Dict avec `path`, `changes` (list), `client_name`, `parsed`, ou `error`.
    """
    try:
        src = _resolve_config(source_path)
    except ValueError as e:
        return {"error": str(e)}
    if not src.exists():
        return {"error": f"config source introuvable : {source_path}"}

    try:
        cfg = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        return {"error": f"YAML source invalide : {e}"}

    if overrides:
        bad = set(overrides) - OVERRIDES_AUTORISES
        if bad:
            return {
                "error": (
                    f"overrides non autorisés : {sorted(bad)}. "
                    f"Valides : {sorted(OVERRIDES_AUTORISES)}"
                )
            }
        cfg, changes = _appliquer_overrides(cfg, overrides)
        erreurs = [c for c in changes if c.startswith("ERREUR")]
        if erreurs:
            return {"error": "; ".join(erreurs)}
    else:
        changes = []

    # Sanitise le nom de fichier (pas de traversal + caractères safe)
    name = Path(save_as).name
    base, _, ext = name.rpartition(".")
    if ext.lower() in ("yaml", "yml"):
        stem = base
        suffix = "." + ext
    else:
        stem = name
        suffix = ".yaml"
    if not stem or not _SAVE_AS_RE.match(stem):
        return {
            "error": (
                f"save_as invalide : '{save_as}'. Lettres/chiffres/tiret/"
                "underscore/point uniquement."
            )
        }

    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    cible = GENERATED_ROOT / f"{stem}{suffix}"

    # Anti-collision : si le fichier existe, suffixe avec timestamp.
    # Les noms générés depuis Streamlit ou l'agent peuvent collisionner
    # quand plusieurs runs partagent la même valeur par défaut.
    if cible.exists():
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        cible = GENERATED_ROOT / f"{stem}-{ts}{suffix}"

    contenu = yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False)
    cible.write_text(contenu, encoding="utf-8")

    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(PROJECT_ROOT))
        except ValueError:
            return str(p)

    return {
        "path": _rel(cible),
        "source": _rel(src),
        "client_name": cfg.get("run", {}).get("client_name"),
        "changes": changes,
        "note": (
            "Config générée dans data/agent/configs/ (sandbox, gitignored). "
            "Utilisable directement avec run_pipeline. Pour la versionner, "
            "déplace-la dans config/."
        ),
    }


def _lire_csv(path: Path) -> list[dict]:
    # utf-8-sig pour tolérer BOM (cas import/export Excel France).
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def compare_sessions(session_a: str, session_b: str) -> dict[str, Any]:
    """Compare la qualité de 2 sessions sur leur étage 3.

    Renvoie les métriques par session + un delta orienté (B - A) avec
    une recommandation textuelle.
    """
    out: dict[str, Any] = {"session_a": session_a, "session_b": session_b}
    metriques = {}
    for label, sid in (("a", session_a), ("b", session_b)):
        dossier = OUTPUT_ROOT / sid
        if not dossier.is_dir():
            return {"error": f"session inconnue : '{sid}'"}
        fichier_l3 = dossier / STAGE_FILES["3"]
        if not fichier_l3.exists():
            return {
                "error": (
                    f"session '{sid}' n'a pas d'étage 3 — lance L1+L2+L3 "
                    "avant de comparer."
                )
            }
        rows = _lire_csv(fichier_l3)
        metriques[label] = _metriques_l3(rows)

    m_a = metriques["a"]
    m_b = metriques["b"]
    deltas = {
        "row_count": m_b["row_count"] - m_a["row_count"],
        "pct_siren_matche": round(
            m_b["pct_siren_matche"] - m_a["pct_siren_matche"], 1
        ),
        "pct_dirigeant_identifie": round(
            m_b["pct_dirigeant_identifie"] - m_a["pct_dirigeant_identifie"], 1
        ),
        "pct_email_scrape": round(
            m_b["pct_email_scrape"] - m_a["pct_email_scrape"], 1
        ),
    }

    # Recommandation simple : on agrège SIREN+dirigeant+email
    score_a = (
        m_a["pct_siren_matche"]
        + m_a["pct_dirigeant_identifie"]
        + m_a["pct_email_scrape"]
    )
    score_b = (
        m_b["pct_siren_matche"]
        + m_b["pct_dirigeant_identifie"]
        + m_b["pct_email_scrape"]
    )
    if abs(score_b - score_a) < 5:
        verdict = "qualité équivalente entre les deux sessions"
    elif score_b > score_a:
        verdict = f"session B meilleure de {round(score_b - score_a, 1)} pts cumulés"
    else:
        verdict = f"session A meilleure de {round(score_a - score_b, 1)} pts cumulés"

    out["metriques_a"] = m_a
    out["metriques_b"] = m_b
    out["delta_b_moins_a"] = deltas
    out["verdict"] = verdict
    return out


SCHEMAS = [
    {
        "name": "clone_config",
        "description": (
            "Duplique un config YAML existant avec overrides ciblés "
            "(zone, secteurs, volume, budget, client_name). Écrit le "
            "nouveau YAML dans `data/agent/configs/` (sandbox, gitignored). "
            "Utilisable immédiatement avec run_pipeline. Sert à relancer "
            "une recherche similaire dans une autre zone géographique ou "
            "avec un autre volume cible. Garde-fou : ne touche jamais aux "
            "configs du dossier `config/` versionnés."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": (
                        "Config source (sous config/, ex 'client_rossini.yaml')."
                    ),
                },
                "save_as": {
                    "type": "string",
                    "description": (
                        "Nom du fichier généré (sans extension ou avec .yaml). "
                        "Ex 'rossini_62' → data/agent/configs/rossini_62.yaml."
                    ),
                },
                "overrides": {
                    "type": "object",
                    "description": (
                        "Modifications à appliquer. Clés autorisées : "
                        "client_name (str), zone_codes (list de str ou str CSV), "
                        "zone_type (str), rayon_par_point_km (int), "
                        "pas_grille_km (int), secteurs (list de str ou list "
                        "de dicts), volume_cible (int), budget_max_eur (float)."
                    ),
                },
            },
            "required": ["source_path", "save_as"],
        },
    },
    {
        "name": "compare_sessions",
        "description": (
            "Compare la qualité de 2 sessions de prospection sur leur "
            "étage 3 (% SIREN matché, % dirigeant, % email). Renvoie les "
            "métriques détaillées, le delta orienté (B - A) et une "
            "recommandation textuelle. Utile pour décider quelle zone "
            "ou quel paramétrage tape le mieux."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_a": {
                    "type": "string",
                    "description": "Première session (référence).",
                },
                "session_b": {
                    "type": "string",
                    "description": "Seconde session (comparaison).",
                },
            },
            "required": ["session_a", "session_b"],
        },
    },
]

DISPATCH = {
    "clone_config": clone_config,
    "compare_sessions": compare_sessions,
}
