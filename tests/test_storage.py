"""Tests des backends de persistance des sessions (storage/).

Le backend Supabase est mocké via MagicMock pour ne dépendre d'aucune
clé/serveur réel. On valide le contrat : tar+gzip, upload, download,
list, delete, gestion d'erreur.
"""

from __future__ import annotations

import io
import tarfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from renoboost_leads.storage import get_storage
from renoboost_leads.storage.local import LocalSessionStorage
from renoboost_leads.storage.supabase_backend import (
    SupabaseSessionStorage,
    _build_tarball,
    _extract_tarball,
)


@pytest.fixture
def fake_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirige PROJECT_ROOT vers tmp pour ne pas polluer data/output/."""
    from renoboost_leads.storage import local as local_mod
    from renoboost_leads.storage import supabase_backend as sb_mod

    monkeypatch.setattr(local_mod, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(sb_mod, "PROJECT_ROOT", tmp_path)
    (tmp_path / "data" / "output").mkdir(parents=True)
    return tmp_path


def _create_session(root: Path, sid: str) -> Path:
    """Crée une fausse session avec 2 CSV et 1 json."""
    d = root / "data" / "output" / sid
    d.mkdir(parents=True)
    (d / "etage1_decouverte.csv").write_text("nom,siren\nA,1\n", encoding="utf-8")
    (d / "etage3_contacts.csv").write_text("nom,email\nA,a@b.fr\n", encoding="utf-8")
    (d / "run_stats.json").write_text('{"campaign": "t"}', encoding="utf-8")
    return d


# ── tarball helpers ───────────────────────────────────────────────


def test_build_tarball_contient_les_fichiers(fake_root: Path) -> None:
    d = _create_session(fake_root, "s_tar")
    data = _build_tarball(d)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        noms = sorted(m.name for m in tar.getmembers() if m.isfile())
    assert "s_tar/etage1_decouverte.csv" in noms
    assert "s_tar/etage3_contacts.csv" in noms
    assert "s_tar/run_stats.json" in noms


def test_extract_tarball_round_trip(fake_root: Path, tmp_path: Path) -> None:
    d = _create_session(fake_root, "s_rt")
    data = _build_tarball(d)
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()
    extrait = _extract_tarball(data, extract_dir)
    assert extrait == extract_dir / "s_rt"
    assert (extrait / "etage1_decouverte.csv").read_text(encoding="utf-8").startswith("nom,siren")


def test_extract_tarball_rejette_path_traversal(tmp_path: Path) -> None:
    """Sécurité : un tar contenant ../ doit être refusé."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="../escape.txt")
        info.size = 4
        tar.addfile(info, io.BytesIO(b"hack"))
    with pytest.raises(ValueError, match="suspect"):
        _extract_tarball(buf.getvalue(), tmp_path)


# ── LocalSessionStorage ───────────────────────────────────────────


def test_local_upload_session_inconnue(fake_root: Path) -> None:
    s = LocalSessionStorage()
    res = s.upload_session("nope")
    assert "error" in res


def test_local_upload_session_existante_skip(fake_root: Path) -> None:
    _create_session(fake_root, "s_ok")
    s = LocalSessionStorage()
    res = s.upload_session("s_ok")
    assert res["ok"] is True
    assert res["skipped"] is True
    assert res["backend"] == "local"


def test_local_list_sessions(fake_root: Path) -> None:
    _create_session(fake_root, "s_a")
    _create_session(fake_root, "s_b")
    s = LocalSessionStorage()
    res = s.list_remote_sessions()
    assert set(res["sessions"]) == {"s_a", "s_b"}


# ── SupabaseSessionStorage (mocké) ────────────────────────────────


def _fake_supabase_client(bucket_mock: MagicMock) -> MagicMock:
    client = MagicMock()
    storage_ns = MagicMock()
    storage_ns.from_ = MagicMock(return_value=bucket_mock)
    client.storage = storage_ns
    return client


def test_supabase_upload_session(fake_root: Path) -> None:
    _create_session(fake_root, "s_up")
    bucket = MagicMock()
    with patch("supabase.create_client") as mock_create:
        mock_create.return_value = _fake_supabase_client(bucket)
        storage = SupabaseSessionStorage(
            url="https://x.co", service_role_key="k", bucket="sessions"
        )
        res = storage.upload_session("s_up")
    assert res["ok"] is True
    assert res["backend"] == "supabase"
    assert res["object_path"] == "s_up.tar.gz"
    assert res["bytes_uploaded"] > 0
    bucket.upload.assert_called_once()
    args, kwargs = bucket.upload.call_args
    assert kwargs["path"] == "s_up.tar.gz"
    assert isinstance(kwargs["file"], bytes)


def test_supabase_upload_session_inconnue(fake_root: Path) -> None:
    bucket = MagicMock()
    with patch("supabase.create_client") as mock_create:
        mock_create.return_value = _fake_supabase_client(bucket)
        storage = SupabaseSessionStorage(url="https://x.co", service_role_key="k", bucket="b")
        res = storage.upload_session("nope")
    assert "error" in res
    bucket.upload.assert_not_called()


def test_supabase_upload_remonte_erreur_clientside(fake_root: Path) -> None:
    _create_session(fake_root, "s_err")
    bucket = MagicMock()
    bucket.upload.side_effect = RuntimeError("403 Forbidden")
    with patch("supabase.create_client") as mock_create:
        mock_create.return_value = _fake_supabase_client(bucket)
        storage = SupabaseSessionStorage(url="https://x.co", service_role_key="k", bucket="b")
        res = storage.upload_session("s_err")
    assert "error" in res
    assert "403" in res["error"]


def test_supabase_download_session(fake_root: Path) -> None:
    # On construit d'abord un tarball valide pour simuler la réponse Supabase
    src = _create_session(fake_root, "s_dl")
    tarball = _build_tarball(src)
    # Supprime la session locale pour vérifier que download la recrée
    import shutil
    shutil.rmtree(src)

    bucket = MagicMock()
    bucket.download.return_value = tarball
    with patch("supabase.create_client") as mock_create:
        mock_create.return_value = _fake_supabase_client(bucket)
        storage = SupabaseSessionStorage(url="https://x.co", service_role_key="k", bucket="b")
        res = storage.download_session("s_dl")
    assert res["ok"] is True
    cible = fake_root / "data" / "output" / "s_dl"
    assert cible.is_dir()
    assert (cible / "etage1_decouverte.csv").exists()


def test_supabase_download_tarball_invalide(fake_root: Path) -> None:
    bucket = MagicMock()
    bucket.download.return_value = b"not a tarball"
    with patch("supabase.create_client") as mock_create:
        mock_create.return_value = _fake_supabase_client(bucket)
        storage = SupabaseSessionStorage(url="https://x.co", service_role_key="k", bucket="b")
        res = storage.download_session("s_bad")
    assert "error" in res
    assert "tarball" in res["error"].lower() or "invalide" in res["error"].lower()


def test_supabase_list_sessions(fake_root: Path) -> None:
    bucket = MagicMock()
    bucket.list.return_value = [
        {"name": "s_a.tar.gz"},
        {"name": "s_b.tar.gz"},
        {"name": "ignore_moi.txt"},  # filtré
    ]
    with patch("supabase.create_client") as mock_create:
        mock_create.return_value = _fake_supabase_client(bucket)
        storage = SupabaseSessionStorage(url="https://x.co", service_role_key="k", bucket="b")
        res = storage.list_remote_sessions()
    assert set(res["sessions"]) == {"s_a", "s_b"}


def test_supabase_delete_session(fake_root: Path) -> None:
    bucket = MagicMock()
    with patch("supabase.create_client") as mock_create:
        mock_create.return_value = _fake_supabase_client(bucket)
        storage = SupabaseSessionStorage(url="https://x.co", service_role_key="k", bucket="b")
        res = storage.delete_remote_session("s_del")
    assert res["ok"] is True
    bucket.remove.assert_called_once_with(["s_del.tar.gz"])


def test_supabase_from_settings_refuse_conf_incomplete(
    fake_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from renoboost_leads.settings import Settings

    settings = Settings(storage_backend="local")  # ← pas activé
    with pytest.raises(RuntimeError, match="non configuré"):
        SupabaseSessionStorage.from_settings(settings)


# ── factory get_storage() ─────────────────────────────────────────


def test_get_storage_local_par_defaut(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sans config Supabase, get_storage() renvoie le backend local."""
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    s = get_storage()
    assert s.backend_name == "local"


def test_get_storage_supabase_quand_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")
    with patch("supabase.create_client") as mock_create:
        mock_create.return_value = MagicMock()
        s = get_storage()
    assert s.backend_name == "supabase"
