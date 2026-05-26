"""Chargement, validation et sauvegarde des campagnes (`campagnes/<id>/campagne.yaml`)."""

from __future__ import annotations

from pathlib import Path

import yaml

from ..verticale.loader import VERTICALES_DIR, load_verticale
from .schema import Campagne

CAMPAGNES_DIR = Path("campagnes")


def load_campagne(campagne_id: str, base_dir: Path = CAMPAGNES_DIR) -> Campagne:
    """Charge et valide une campagne par son id.

    Lève :
        FileNotFoundError si le fichier n'existe pas
        yaml.YAMLError si le YAML est mal formé
        pydantic.ValidationError si le contenu ne respecte pas le schéma
        ValueError si l'id du fichier ne correspond pas au dossier
    """
    yaml_path = base_dir / campagne_id / "campagne.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Campagne introuvable : {yaml_path}")

    with yaml_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    if not isinstance(raw, dict):
        raise ValueError(f"Le fichier {yaml_path} doit contenir un objet YAML (dict).")

    campagne = Campagne.model_validate(raw)

    if campagne.id != campagne_id:
        raise ValueError(
            f"Incohérence id : dossier '{campagne_id}' mais campagne.id='{campagne.id}'."
        )

    return campagne


def list_campagnes(base_dir: Path = CAMPAGNES_DIR) -> list[str]:
    """Retourne les ids des campagnes présentes (dossiers avec campagne.yaml)."""
    if not base_dir.exists():
        return []
    return [p.parent.name for p in sorted(base_dir.glob("*/campagne.yaml"))]


def save_campagne(
    campagne: Campagne,
    base_dir: Path = CAMPAGNES_DIR,
    verticales_dir: Path = VERTICALES_DIR,
) -> Path:
    """Écrit `campagnes/<id>/campagne.yaml` après avoir vérifié la verticale.

    La verticale référencée doit exister et être exploitable en V0 (B2B) :
    on ne persiste pas une campagne qui pointe vers une offre introuvable ou
    hors périmètre. `load_verticale` lève `FileNotFoundError` ou
    `VerticaleHorsV0Error` le cas échéant — on laisse remonter.
    """
    load_verticale(campagne.verticale_slug, base_dir=verticales_dir)

    d = base_dir / campagne.id
    d.mkdir(parents=True, exist_ok=True)
    chemin = d / "campagne.yaml"
    contenu = yaml.safe_dump(campagne.model_dump(), allow_unicode=True, sort_keys=False)
    chemin.write_text(contenu, encoding="utf-8")
    return chemin
