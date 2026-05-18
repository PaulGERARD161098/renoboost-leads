"""Outils `read_config` et `propose_config_edit`.

Garde-fou Phase A : l'agent ne peut PAS écrire dans les YAML de prod.
`propose_config_edit` calcule un diff unifié et le retourne au LLM, qui
doit le présenter à l'utilisateur dans sa synthèse. Le user applique
manuellement (ou via une PR plus tard).

`read_config` :
- lit n'importe quel YAML sous `config/` (chroot léger pour éviter
  qu'un prompt-injecté ne fasse lire /etc/passwd)
- limite à 200 KB pour rester dans la fenêtre de tokens

`propose_config_edit` :
- accepte un YAML cible complet (recommandé) ou un patch dict
- calcule diff unifié vs version actuelle
- N'ÉCRIT PAS — renvoie le diff comme `proposed_diff`
"""

from __future__ import annotations

import difflib
from pathlib import Path

import yaml

from ...settings import PROJECT_ROOT

CONFIG_ROOT = PROJECT_ROOT / "config"
MAX_FILE_BYTES = 200_000


def _resolve_config(path: str) -> Path:
    """Force le chemin sous CONFIG_ROOT (rejette tout traversal)."""
    p = Path(path)
    # Refuse explicitement les éléments `..` et chemins absolus hors CONFIG_ROOT
    if ".." in p.parts:
        raise ValueError("chemin hors `config/` interdit (traversal `..`).")
    if p.is_absolute():
        candidate = p.resolve()
    else:
        # Si on n'a pas le préfixe config/, on l'ajoute via basename
        if not str(p).startswith("config" + "/") and not str(p).startswith(
            "config" + "\\"
        ):
            candidate = (CONFIG_ROOT / p.name).resolve()
        else:
            candidate = (PROJECT_ROOT / p).resolve()
    if not str(candidate).startswith(str(CONFIG_ROOT.resolve())):
        raise ValueError(
            f"chemin hors `config/` interdit : {candidate} (limite chroot)."
        )
    return candidate


def read_config(path: str) -> dict:
    """Renvoie le contenu YAML brut + parsé d'une config."""
    try:
        p = _resolve_config(path)
    except ValueError as e:
        return {"error": str(e)}
    if not p.exists():
        return {"error": f"config introuvable : {p.relative_to(PROJECT_ROOT)}"}
    if p.stat().st_size > MAX_FILE_BYTES:
        return {
            "error": f"fichier trop gros ({p.stat().st_size} octets > {MAX_FILE_BYTES})"
        }
    contenu = p.read_text(encoding="utf-8")
    try:
        parsed = yaml.safe_load(contenu)
    except yaml.YAMLError as e:
        parsed = None
        parse_error = str(e)
    else:
        parse_error = None
    return {
        "path": str(p.relative_to(PROJECT_ROOT)),
        "contenu_brut": contenu,
        "parsed": parsed,
        "parse_error": parse_error,
    }


def propose_config_edit(path: str, contenu_cible: str, motif: str = "") -> dict:
    """Calcule un diff unifié vs le YAML actuel — N'ÉCRIT PAS.

    `contenu_cible` = nouveau YAML complet (str). Le diff est destiné à
    être présenté à l'utilisateur pour application manuelle.
    """
    try:
        p = _resolve_config(path)
    except ValueError as e:
        return {"error": str(e)}
    actuel = p.read_text(encoding="utf-8") if p.exists() else ""

    # Validation que le contenu cible est du YAML parseable
    try:
        yaml.safe_load(contenu_cible)
    except yaml.YAMLError as e:
        return {
            "error": f"contenu cible n'est pas du YAML valide : {e}",
        }

    diff = "".join(
        difflib.unified_diff(
            actuel.splitlines(keepends=True),
            contenu_cible.splitlines(keepends=True),
            fromfile=f"a/{p.relative_to(PROJECT_ROOT)}",
            tofile=f"b/{p.relative_to(PROJECT_ROOT)} (proposition)",
            n=3,
        )
    )
    if not diff:
        return {
            "path": str(p.relative_to(PROJECT_ROOT)),
            "motif": motif,
            "proposed_diff": "",
            "message": "Aucune modification — contenu identique à l'existant.",
            "ecrit": False,
        }
    return {
        "path": str(p.relative_to(PROJECT_ROOT)),
        "motif": motif,
        "proposed_diff": diff,
        "ecrit": False,
        "note": (
            "Garde-fou Phase A : aucun fichier n'a été modifié. "
            "Présente ce diff à l'utilisateur pour application manuelle."
        ),
    }


SCHEMAS = [
    {
        "name": "read_config",
        "description": (
            "Lit un fichier YAML de configuration sous `config/`. "
            "Renvoie le contenu brut + parsé. Limite 200 KB. Chroot sur "
            "`config/` (impossible de lire ailleurs)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Nom de fichier ou chemin relatif "
                        "(ex 'pilote_phase1.yaml' ou 'config/agent.yaml')."
                    ),
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "propose_config_edit",
        "description": (
            "Propose une modification d'un YAML de config sans l'écrire. "
            "Renvoie le diff unifié à présenter à l'utilisateur. Garde-fou "
            "Phase A : aucune écriture. Le user applique manuellement."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Fichier cible sous `config/`.",
                },
                "contenu_cible": {
                    "type": "string",
                    "description": "Nouveau contenu YAML complet (string).",
                },
                "motif": {
                    "type": "string",
                    "description": "Pourquoi cette modif (sera loggé au journal).",
                    "default": "",
                },
            },
            "required": ["path", "contenu_cible"],
        },
    },
]

DISPATCH = {
    "read_config": read_config,
    "propose_config_edit": propose_config_edit,
}
