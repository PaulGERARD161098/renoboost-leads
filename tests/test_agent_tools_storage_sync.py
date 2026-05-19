"""Tests de l'outil agent sync_session."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from renoboost_leads.agent.tools.storage_sync import sync_session


def test_sync_up_appelle_upload() -> None:
    fake = MagicMock()
    fake.upload_session.return_value = {"ok": True, "session_id": "s_a"}
    with patch("renoboost_leads.storage.get_storage", return_value=fake):
        res = sync_session("s_a", direction="up")
    assert res["ok"] is True
    fake.upload_session.assert_called_once_with("s_a")


def test_sync_down_appelle_download() -> None:
    fake = MagicMock()
    fake.download_session.return_value = {"ok": True, "session_id": "s_b"}
    with patch("renoboost_leads.storage.get_storage", return_value=fake):
        res = sync_session("s_b", direction="down")
    fake.download_session.assert_called_once_with("s_b")
    assert res["ok"] is True


def test_sync_list_ignore_session_id() -> None:
    fake = MagicMock()
    fake.list_remote_sessions.return_value = {"sessions": ["s_a", "s_b"]}
    with patch("renoboost_leads.storage.get_storage", return_value=fake):
        res = sync_session(session_id=None, direction="list")
    assert res["sessions"] == ["s_a", "s_b"]


def test_sync_up_sans_session_id_erreur() -> None:
    fake = MagicMock()
    with patch("renoboost_leads.storage.get_storage", return_value=fake):
        res = sync_session(session_id=None, direction="up")
    assert "error" in res
    fake.upload_session.assert_not_called()


def test_sync_direction_invalide() -> None:
    fake = MagicMock()
    with patch("renoboost_leads.storage.get_storage", return_value=fake):
        res = sync_session("s_x", direction="sideways")  # type: ignore[arg-type]
    assert "error" in res
    assert "invalide" in res["error"]


def test_outil_enregistre_dans_registry() -> None:
    from renoboost_leads.agent.tools import all_dispatch, all_schemas

    noms = {s["name"] for s in all_schemas()}
    assert "sync_session" in noms
    assert "sync_session" in all_dispatch()
