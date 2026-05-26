"""Tests E2E du sous-groupe CLI `campagnes` (Click runner).

S'appuie sur la campagne réelle `clim-lille-amiens-juin` (verticale clim-pro-b2b).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from renoboost_leads.campagne import Campagne
from renoboost_leads.cli_campagnes import campagnes_group


def test_list_exit0_et_contient_la_campagne() -> None:
    res = CliRunner().invoke(campagnes_group, ["list"])
    assert res.exit_code == 0
    assert "Campagnes disponibles" in res.output
    assert "clim-pro-b2b" in res.output
    assert "departement:59,80" in res.output


def test_show_campagne_existante_avec_config_composee() -> None:
    res = CliRunner().invoke(campagnes_group, ["show", "clim-lille-amiens-juin"])
    assert res.exit_code == 0
    assert "clim-pro-b2b" in res.output
    assert "Config composée" in res.output


def test_show_campagne_introuvable_exit1() -> None:
    res = CliRunner().invoke(campagnes_group, ["show", "nexiste-pas"])
    assert res.exit_code == 1
    assert "introuvable" in res.output


def test_run_compose_persiste_et_invoque_le_pipeline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`campagnes run` doit composer la config puis invoquer `run` (offline)."""
    from renoboost_leads import cli_campagnes as cc

    camp = Campagne.model_validate(
        {
            "campagne": {"id": "camp-test", "verticale_slug": "vert-test"},
            "zone": {"type": "departement", "codes": ["59"]},
            "volume": {"cible": 10},
            "budget": {"max_eur": 5.0},
        }
    )
    cfg_path = tmp_path / "campagne-camp-test.yaml"

    monkeypatch.setattr(cc, "load_campagne", lambda cid: camp)
    monkeypatch.setattr(cc, "load_verticale", lambda slug: object())
    monkeypatch.setattr(cc, "persister_config_lancable", lambda c, v: cfg_path)

    appels: dict = {}

    def _fake_callback(config_path, stages, from_csv_path, dry_run):  # noqa: ANN001
        appels.update(
            config_path=config_path,
            stages=stages,
            from_csv_path=from_csv_path,
            dry_run=dry_run,
        )

    import renoboost_leads.cli as maincli

    monkeypatch.setattr(maincli.run, "callback", _fake_callback)

    res = CliRunner().invoke(
        cc.campagnes_group, ["run", "camp-test", "--stages", "1", "--dry-run"]
    )
    assert res.exit_code == 0, res.output
    assert appels == {
        "config_path": cfg_path,
        "stages": "1",
        "from_csv_path": None,
        "dry_run": True,
    }
