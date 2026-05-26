"""Tests E2E du sous-groupe CLI `verticales` (Click runner)."""

from __future__ import annotations

from click.testing import CliRunner

from renoboost_leads.cli_verticales import verticales_group


def test_list_exit0_et_contient_les_verticales() -> None:
    res = CliRunner().invoke(verticales_group, ["list"])
    assert res.exit_code == 0
    assert "irve-flottes-b2b" in res.output
    assert "Verticales disponibles" in res.output


def test_show_verticale_existante() -> None:
    res = CliRunner().invoke(verticales_group, ["show", "irve-flottes-b2b"])
    assert res.exit_code == 0
    assert "Bornes IRVE" in res.output
    assert "b2b" in res.output


def test_show_verticale_introuvable_exit1() -> None:
    res = CliRunner().invoke(verticales_group, ["show", "nexiste-pas"])
    assert res.exit_code == 1
    assert "introuvable" in res.output
