"""Tests de l'outil run_pipeline (subprocess mocké)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from renoboost_leads.agent.tools import pipeline as p


@pytest.fixture
def cfg_file(tmp_path: Path) -> Path:
    p = tmp_path / "fake.yaml"
    p.write_text("run:\n  client_name: test\n", encoding="utf-8")
    return p


def test_config_inexistante(tmp_path: Path) -> None:
    res = p.run_pipeline(str(tmp_path / "nope.yaml"))
    assert "error" in res
    assert "introuvable" in res["error"]


def test_stages_invalide(cfg_file: Path) -> None:
    res = p.run_pipeline(str(cfg_file), stages="9,X")
    assert "error" in res
    assert "invalides" in res["error"]


def test_stages_vide(cfg_file: Path) -> None:
    res = p.run_pipeline(str(cfg_file), stages=",,")
    assert "error" in res


def test_subprocess_ok(cfg_file: Path) -> None:
    fake = MagicMock(returncode=0, stdout="line1\nline2\n", stderr="")
    with patch("renoboost_leads.agent.tools.pipeline.subprocess.run", return_value=fake) as m:
        res = p.run_pipeline(str(cfg_file), stages="1,2", dry_run=True)
    assert res["ok"] is True
    assert res["returncode"] == 0
    assert "line2" in res["stdout_tail"]
    args = m.call_args.args[0]
    assert "--dry-run" in args
    assert "1,2" in args


def test_subprocess_echec(cfg_file: Path) -> None:
    fake = MagicMock(returncode=2, stdout="", stderr="erreur X")
    with patch("renoboost_leads.agent.tools.pipeline.subprocess.run", return_value=fake):
        res = p.run_pipeline(str(cfg_file))
    assert res["ok"] is False
    assert "erreur X" in res["stderr_tail"]


def test_subprocess_timeout(cfg_file: Path) -> None:
    with patch(
        "renoboost_leads.agent.tools.pipeline.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="x", timeout=10),
    ):
        res = p.run_pipeline(str(cfg_file), timeout_s=10)
    assert "error" in res
    assert "timeout" in res["error"].lower()
