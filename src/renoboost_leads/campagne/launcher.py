"""Préparation du lancement d'une campagne.

Pont entre l'objet `Campagne` et le pipeline existant : compose le
`CampaignConfig` (via le composer) puis le persiste en `config/campagne-<id>.yaml`.
Ce fichier est ensuite consommé tel quel par la commande `run` (aucune
duplication de la logique pipeline).

Ce module reste **pur** (composition + écriture de fichier) : il n'invoque pas
le pipeline lui-même, pour éviter tout import circulaire avec `cli`. C'est la
couche CLI / UI qui appelle `run` avec le chemin retourné.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ..settings import PROJECT_ROOT
from ..verticale.schema import Verticale
from .composer import composer_campaign_config
from .schema import Campagne

CONFIG_DIR = PROJECT_ROOT / "config"


def persister_config_lancable(
    campagne: Campagne,
    verticale: Verticale,
    dest_dir: Path = CONFIG_DIR,
) -> Path:
    """Compose et écrit un `config/campagne-<id>.yaml` lançable par `run`.

    Retourne le chemin du fichier écrit. Lève `ValueError` si la verticale ne
    correspond pas au slug référencé par la campagne (via le composer).
    """
    cfg = composer_campaign_config(campagne, verticale)
    dest_dir.mkdir(parents=True, exist_ok=True)
    chemin = dest_dir / f"campagne-{campagne.id}.yaml"
    contenu = yaml.safe_dump(cfg.model_dump(), allow_unicode=True, sort_keys=False)
    chemin.write_text(contenu, encoding="utf-8")
    return chemin
