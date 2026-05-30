"""Tests du câblage verticale → run (`_appliquer_verticale`).

La verticale est la source de vérité du ciblage : ses `secteurs_places` (L1) et
`filtres_entreprise` (L2) surchargent ceux de la config, garantissant leur
cohérence (anti-décalage L1↔NAF).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from renoboost_leads.cli import _appliquer_verticale
from renoboost_leads.config_loader import load_campaign_config
from renoboost_leads.verticale import load_verticale

_CONFIG_BASE = Path("config/client_rossini.yaml")


def test_applique_le_ciblage_de_la_verticale() -> None:
    cfg = load_campaign_config(_CONFIG_BASE)
    verticale = load_verticale("irve-flottes-b2b")

    # Pré-condition : le ciblage de base diffère de celui de la verticale.
    _appliquer_verticale(cfg, "irve-flottes-b2b")

    assert cfg.secteurs == verticale.cibles.secteurs_places
    assert cfg.filtres_entreprise == verticale.cibles.filtres_entreprise
    assert len(cfg.secteurs) >= 1


def test_verticale_introuvable_termine_avec_code_2() -> None:
    cfg = load_campaign_config(_CONFIG_BASE)
    with pytest.raises(SystemExit) as exc:
        _appliquer_verticale(cfg, "verticale-qui-nexiste-pas")
    assert exc.value.code == 2
