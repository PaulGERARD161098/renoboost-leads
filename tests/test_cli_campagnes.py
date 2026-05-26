"""Tests E2E du sous-groupe CLI `campagnes` (Click runner).

S'appuie sur la campagne réelle `clim-lille-amiens-juin` (verticale clim-pro-b2b).
"""

from __future__ import annotations

from click.testing import CliRunner

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
