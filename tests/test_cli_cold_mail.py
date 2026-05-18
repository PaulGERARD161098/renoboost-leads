"""Tests E2E des commandes CLI cold-mail (Click runner + dry-run)."""

from __future__ import annotations

from click.testing import CliRunner

from renoboost_leads.cli_cold_mail import cold_mail_group
from renoboost_leads.instantly.staging import (
    StagedItem,
    Staging,
    StagingStore,
)


def _make_staging(staging_id: str = "stg_test1") -> Staging:
    return Staging(
        staging_id=staging_id,
        secteur="compta",
        session_id="20260518-x",
        from_email="paul@x.fr",
        items=[
            StagedItem(
                lead_id="100",
                email_dest="a@x.fr",
                nom_dest="Alice",
                sujet="S1",
                corps="Corps A",
            ),
            StagedItem(
                lead_id="200",
                email_dest="b@x.fr",
                nom_dest="Bob",
                sujet="S2",
                corps="Corps B",
            ),
        ],
    )


def test_list_vide() -> None:
    runner = CliRunner()
    res = runner.invoke(cold_mail_group, ["list"])
    assert res.exit_code == 0
    assert "Aucun" in res.output or "stg_" not in res.output


def test_list_avec_stagings() -> None:
    StagingStore().save(_make_staging())
    runner = CliRunner(env={"COLUMNS": "200", "FORCE_COLOR": "0", "NO_COLOR": "1"})
    res = runner.invoke(cold_mail_group, ["list"])
    assert res.exit_code == 0
    assert "stg_test1" in res.output
    assert "compta" in res.output


def test_show_inexistant() -> None:
    runner = CliRunner()
    res = runner.invoke(cold_mail_group, ["show", "stg_fantome"])
    assert res.exit_code != 0
    assert "absent" in res.output or "✗" in res.output


def test_show_ok() -> None:
    StagingStore().save(_make_staging("stg_show"))
    runner = CliRunner()
    res = runner.invoke(cold_mail_group, ["show", "stg_show"])
    assert res.exit_code == 0
    assert "a@x.fr" in res.output
    assert "b@x.fr" in res.output


def test_validate_marque_etat() -> None:
    StagingStore().save(_make_staging("stg_v"))
    runner = CliRunner()
    res = runner.invoke(
        cold_mail_group,
        ["validate", "--staging-id", "stg_v", "--lead-id", "100"],
    )
    assert res.exit_code == 0
    s = StagingStore().load("stg_v")
    item = next(i for i in s.items if i.lead_id == "100")
    assert item.etat == "valide"


def test_refuse_marque_etat() -> None:
    StagingStore().save(_make_staging("stg_r"))
    runner = CliRunner()
    res = runner.invoke(
        cold_mail_group,
        ["refuse", "--staging-id", "stg_r", "--lead-id", "200"],
    )
    assert res.exit_code == 0
    s = StagingStore().load("stg_r")
    item = next(i for i in s.items if i.lead_id == "200")
    assert item.etat == "refuse"


def test_validate_lead_inconnu() -> None:
    StagingStore().save(_make_staging("stg_vi"))
    runner = CliRunner()
    res = runner.invoke(
        cold_mail_group,
        ["validate", "--staging-id", "stg_vi", "--lead-id", "fantome"],
    )
    assert res.exit_code != 0


def test_send_aucun_valide() -> None:
    StagingStore().save(_make_staging("stg_send_empty"))
    runner = CliRunner()
    res = runner.invoke(cold_mail_group, ["send", "--staging-id", "stg_send_empty"])
    assert res.exit_code == 0
    assert "rien à envoyer" in res.output or "⚠" in res.output


def test_send_avec_valide_dry_run() -> None:
    StagingStore().save(_make_staging("stg_send_ok"))
    StagingStore().set_etat("stg_send_ok", "100", "valide")
    runner = CliRunner()
    res = runner.invoke(cold_mail_group, ["send", "--staging-id", "stg_send_ok"])
    assert res.exit_code == 0
    assert "DRY-RUN" in res.output
    # L'item est passé en envoyé
    s = StagingStore().load("stg_send_ok")
    item = next(i for i in s.items if i.lead_id == "100")
    assert item.etat == "envoye"


def test_metrics_dry_run() -> None:
    runner = CliRunner()
    res = runner.invoke(cold_mail_group, ["metrics", "--campaign-id", "x"])
    assert res.exit_code == 0
    assert "dry-run" in res.output.lower() or "Sent" in res.output
