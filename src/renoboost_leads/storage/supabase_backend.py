"""Backend de persistance Supabase Storage.

Stratégie : une session = un objet `<session_id>.tar.gz` dans le bucket
configuré. Upload = tar+gzip du dossier `data/output/<session_id>/` puis
PUT vers Supabase. Download = inverse.

Pourquoi tar.gz et pas un fichier par CSV ?
- Atomique : pas de session "moitié uploadée" visible.
- Économe : compression ~5x sur les CSV texte.
- Simple : un seul appel API par session, pas de listage récursif.

Limitation : à chaque mutation (run, enrich, score), on ré-uploade tout le
tar.gz de la session. Une session ~50 leads fait ~10-30 Ko compressée, donc
on reste dans le tier gratuit Supabase (1 Go) très largement.
"""

from __future__ import annotations

import io
import logging
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from ..settings import PROJECT_ROOT, Settings

logger = logging.getLogger(__name__)

_TAR_SUFFIX = ".tar.gz"


def _sessions_root() -> Path:
    return PROJECT_ROOT / "data" / "output"


def _build_tarball(session_dir: Path) -> bytes:
    """Compresse le dossier en tar.gz et renvoie les bytes.

    Le tarball contient `<session_id>/` comme racine pour que l'extraction
    recrée bien la même arborescence côté téléchargement.
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(session_dir, arcname=session_dir.name)
    return buf.getvalue()


def _extract_tarball(data: bytes, target_root: Path) -> Path:
    """Extrait un tar.gz et renvoie le dossier session écrit."""
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        # Sécurité : refuse les chemins absolus ou ../ qui sortiraient
        # de target_root (CVE-2007-4559 style tarbomb / path traversal).
        for member in tar.getmembers():
            name = member.name
            if name.startswith("/") or ".." in Path(name).parts:
                raise ValueError(f"chemin suspect dans le tarball : {name!r}")
        tar.extractall(target_root, filter="data")  # filter="data" Python 3.12+
    # Le tarball racine est `<session_id>/`, on renvoie ce dossier
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar2:
        racines = {Path(m.name).parts[0] for m in tar2.getmembers()}
    if len(racines) == 1:
        return target_root / next(iter(racines))
    return target_root


class SupabaseSessionStorage:
    """Backend Supabase Storage — upload/download de tar.gz par session."""

    backend_name = "supabase"

    def __init__(self, url: str, service_role_key: str, bucket: str) -> None:
        # Import paresseux : le package supabase est optionnel.
        from supabase import create_client

        self._client = create_client(url, service_role_key)
        self._bucket_name = bucket

    @classmethod
    def from_settings(cls, settings: Settings) -> SupabaseSessionStorage:
        if not settings.has_supabase_storage():
            raise RuntimeError(
                "Supabase Storage non configuré : il faut SUPABASE_URL + "
                "SUPABASE_SERVICE_ROLE_KEY + STORAGE_BACKEND=supabase. "
                "Cf .env.example."
            )
        assert settings.supabase_url is not None  # noqa: S101 — validé par has_*
        assert settings.supabase_service_role_key is not None  # noqa: S101
        return cls(
            url=settings.supabase_url,
            service_role_key=settings.supabase_service_role_key.get_secret_value(),
            bucket=settings.supabase_bucket,
        )

    @property
    def _bucket(self):  # noqa: ANN202
        return self._client.storage.from_(self._bucket_name)

    def _object_path(self, session_id: str) -> str:
        return f"{session_id}{_TAR_SUFFIX}"

    # ─── Protocol implementation ───

    def upload_session(self, session_id: str) -> dict[str, Any]:
        dossier = _sessions_root() / session_id
        if not dossier.is_dir():
            return {"error": f"session inconnue : '{session_id}'", "backend": "supabase"}

        data = _build_tarball(dossier)
        path = self._object_path(session_id)

        try:
            # `upsert=true` pour ré-uploader sans conflit
            self._bucket.upload(
                path=path,
                file=data,
                file_options={"content-type": "application/gzip", "upsert": "true"},
            )
        except Exception as e:  # noqa: BLE001 — surface clean au runner agent
            logger.exception("Échec upload Supabase pour %s", session_id)
            return {
                "error": f"upload Supabase échoué : {type(e).__name__}: {e}",
                "backend": "supabase",
                "session_id": session_id,
            }

        return {
            "backend": "supabase",
            "session_id": session_id,
            "ok": True,
            "bytes_uploaded": len(data),
            "object_path": path,
        }

    def download_session(self, session_id: str) -> dict[str, Any]:
        path = self._object_path(session_id)
        try:
            data = self._bucket.download(path)
        except Exception as e:  # noqa: BLE001
            logger.exception("Échec download Supabase pour %s", session_id)
            return {
                "error": f"download Supabase échoué : {type(e).__name__}: {e}",
                "backend": "supabase",
                "session_id": session_id,
            }

        if not isinstance(data, bytes):
            return {
                "error": f"réponse Supabase inattendue : {type(data).__name__}",
                "backend": "supabase",
                "session_id": session_id,
            }

        # On extrait dans un dossier temp puis on rsync vers data/output/
        # pour éviter une session corrompue si extract plante au milieu.
        target_root = _sessions_root()
        target_root.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            try:
                _extract_tarball(data, tmp_path)
            except (ValueError, tarfile.TarError) as e:
                return {
                    "error": f"tarball invalide : {e}",
                    "backend": "supabase",
                    "session_id": session_id,
                }
            extrait = tmp_path / session_id
            if not extrait.is_dir():
                return {
                    "error": f"tarball ne contient pas {session_id}/ à la racine",
                    "backend": "supabase",
                    "session_id": session_id,
                }
            cible = target_root / session_id
            if cible.exists():
                shutil.rmtree(cible)
            shutil.move(str(extrait), str(cible))

        return {
            "backend": "supabase",
            "session_id": session_id,
            "ok": True,
            "bytes_downloaded": len(data),
            "local_path": str((_sessions_root() / session_id).relative_to(PROJECT_ROOT)),
        }

    def list_remote_sessions(self) -> dict[str, Any]:
        try:
            items = self._bucket.list()
        except Exception as e:  # noqa: BLE001
            logger.exception("Échec list Supabase")
            return {
                "error": f"list Supabase échoué : {type(e).__name__}: {e}",
                "backend": "supabase",
            }

        ids = []
        for it in items:
            name = it.get("name") if isinstance(it, dict) else None
            if name and name.endswith(_TAR_SUFFIX):
                ids.append(name[: -len(_TAR_SUFFIX)])
        return {"backend": "supabase", "sessions": sorted(ids, reverse=True)}

    def delete_remote_session(self, session_id: str) -> dict[str, Any]:
        path = self._object_path(session_id)
        try:
            self._bucket.remove([path])
        except Exception as e:  # noqa: BLE001
            return {
                "error": f"delete Supabase échoué : {type(e).__name__}: {e}",
                "backend": "supabase",
                "session_id": session_id,
            }
        return {
            "backend": "supabase",
            "session_id": session_id,
            "ok": True,
            "deleted_object": path,
        }
