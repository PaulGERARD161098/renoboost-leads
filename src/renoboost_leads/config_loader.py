"""Chargement et validation des fichiers de config YAML."""

from __future__ import annotations

from pathlib import Path

import yaml

from .models import CampaignConfig


def load_campaign_config(yaml_path: Path) -> CampaignConfig:
    """Charge un fichier YAML et le valide via Pydantic.

    Lève :
        FileNotFoundError si le fichier n'existe pas
        yaml.YAMLError si le YAML est mal formé
        pydantic.ValidationError si le contenu ne respecte pas le schéma
    """
    if not yaml_path.exists():
        raise FileNotFoundError(f"Config YAML introuvable : {yaml_path}")

    with yaml_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    if not isinstance(raw, dict):
        raise ValueError(f"Le fichier {yaml_path} doit contenir un objet YAML (dict).")

    return CampaignConfig.model_validate(raw)
