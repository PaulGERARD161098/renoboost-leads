"""Tests des outils read_config et propose_config_edit."""

from __future__ import annotations

from pathlib import Path

import pytest

from renoboost_leads.agent.tools import config as cfg


@pytest.fixture
def fake_config_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "config"
    root.mkdir()
    monkeypatch.setattr(cfg, "CONFIG_ROOT", root)
    monkeypatch.setattr(cfg, "PROJECT_ROOT", tmp_path)
    return root


def test_read_config_inconnu(fake_config_root: Path) -> None:
    res = cfg.read_config("nope.yaml")
    assert "error" in res
    assert "introuvable" in res["error"]


def test_read_config_ok(fake_config_root: Path) -> None:
    (fake_config_root / "x.yaml").write_text("a: 1\nb: deux\n", encoding="utf-8")
    res = cfg.read_config("x.yaml")
    assert res["parsed"] == {"a": 1, "b": "deux"}
    assert "a: 1" in res["contenu_brut"]
    assert res["parse_error"] is None


def test_read_config_yaml_invalide(fake_config_root: Path) -> None:
    (fake_config_root / "bad.yaml").write_text("a: [unclosed", encoding="utf-8")
    res = cfg.read_config("bad.yaml")
    assert res["parsed"] is None
    assert res["parse_error"] is not None


def test_read_config_chroot_bloque_exterieur(
    fake_config_root: Path, tmp_path: Path
) -> None:
    # Tente d'accéder à un fichier hors config/
    (tmp_path / "secret.txt").write_text("nope", encoding="utf-8")
    res = cfg.read_config("../secret.txt")
    assert "error" in res
    assert "chroot" in res["error"] or "interdit" in res["error"]


def test_read_config_taille_limite(
    fake_config_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cfg, "MAX_FILE_BYTES", 10)
    (fake_config_root / "gros.yaml").write_text("a: " + "x" * 100, encoding="utf-8")
    res = cfg.read_config("gros.yaml")
    assert "error" in res
    assert "trop gros" in res["error"]


def test_propose_edit_diff(fake_config_root: Path) -> None:
    (fake_config_root / "p.yaml").write_text("a: 1\nb: 2\n", encoding="utf-8")
    res = cfg.propose_config_edit("p.yaml", "a: 1\nb: 99\nc: 3\n", motif="ajustement")
    assert res["ecrit"] is False
    assert "b: 2" in res["proposed_diff"]
    assert "b: 99" in res["proposed_diff"]
    assert res["motif"] == "ajustement"
    # Le fichier n'a PAS été modifié
    assert (fake_config_root / "p.yaml").read_text(encoding="utf-8") == "a: 1\nb: 2\n"


def test_propose_edit_identique(fake_config_root: Path) -> None:
    (fake_config_root / "p.yaml").write_text("a: 1\n", encoding="utf-8")
    res = cfg.propose_config_edit("p.yaml", "a: 1\n")
    assert res["proposed_diff"] == ""
    assert "identique" in res["message"]


def test_propose_edit_yaml_cible_invalide(fake_config_root: Path) -> None:
    (fake_config_root / "p.yaml").write_text("a: 1\n", encoding="utf-8")
    res = cfg.propose_config_edit("p.yaml", "a: [unclosed")
    assert "error" in res
    assert "YAML" in res["error"]


def test_propose_edit_chroot(fake_config_root: Path, tmp_path: Path) -> None:
    (tmp_path / "exterieur.yaml").write_text("a: 1\n", encoding="utf-8")
    res = cfg.propose_config_edit("../exterieur.yaml", "a: 2\n")
    assert "error" in res
