"""Chargement et validation des verticales (`verticales/<slug>/verticale.yaml`)."""

from __future__ import annotations

from pathlib import Path

import yaml

from .schema import Verticale

VERTICALES_DIR = Path("verticales")


class VerticaleHorsV0Error(ValueError):
    """Verticale dont la cible n'est pas supportée en V0 (B2B uniquement)."""


def load_verticale(slug: str, base_dir: Path = VERTICALES_DIR) -> Verticale:
    """Charge et valide une verticale par son slug.

    Lève :
        FileNotFoundError si le fichier n'existe pas
        yaml.YAMLError si le YAML est mal formé
        pydantic.ValidationError si le contenu ne respecte pas le schéma
        VerticaleHorsV0Error si `cible.type` n'est pas `b2b` (B2C = V1)
        ValueError si le slug du fichier ne correspond pas au dossier
    """
    yaml_path = base_dir / slug / "verticale.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Verticale introuvable : {yaml_path}")

    with yaml_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    if not isinstance(raw, dict):
        raise ValueError(f"Le fichier {yaml_path} doit contenir un objet YAML (dict).")

    verticale = Verticale.model_validate(raw)

    if verticale.slug != slug:
        raise ValueError(
            f"Incohérence slug : dossier '{slug}' mais verticale.slug='{verticale.slug}'."
        )

    if verticale.cible.type != "b2b":
        raise VerticaleHorsV0Error(
            f"Verticale '{slug}' : cible.type='{verticale.cible.type}' non supporté en V0 "
            "(B2B uniquement ; le B2C arrive en V1)."
        )

    return verticale


def list_verticales(base_dir: Path = VERTICALES_DIR) -> list[str]:
    """Retourne les slugs des verticales présentes (dossiers avec verticale.yaml)."""
    if not base_dir.exists():
        return []
    return [p.parent.name for p in sorted(base_dir.glob("*/verticale.yaml"))]
