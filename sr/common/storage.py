"""Storage abstraction: local filesystem, or an S3-compatible object store.

The audio pipeline reads and writes real files (ffmpeg and libsndfile both need
paths), so the object store keeps an ephemeral local scratch directory and syncs
it around those operations:

  * ``path_for(key)``     -> a LOCAL scratch path for ``key`` (may not exist yet)
  * ``ensure_local(key)`` -> download ``key`` into scratch if missing, return path
  * ``persist(key)``      -> upload the scratch file at ``path_for(key)``
  * ``save_wav`` / ``save_bytes`` / ``save_text`` write locally AND persist
  * ``read_stereo`` / ``read_bytes`` ensure-local, then read

For ``LocalStorage`` the scratch directory *is* the store, so ``ensure_local`` and
``persist`` are no-ops and every call behaves exactly as it did before object
storage existed. Selected by ``SR_STORAGE_BACKEND`` (``local`` | ``s3``).
"""

from __future__ import annotations

import abc
import shutil
import tempfile
from pathlib import Path

import numpy as np

from sr.common import dsp
from sr.config import get_settings

_CONTENT_TYPES = {
    ".wav": "audio/wav", ".mp3": "audio/mpeg", ".flac": "audio/flac",
    ".ogg": "audio/ogg", ".opus": "audio/opus", ".m4a": "audio/mp4",
    ".webm": "audio/webm", ".mp4": "audio/mp4", ".json": "application/json",
}


def _content_type(key: str) -> str:
    return _CONTENT_TYPES.get(Path(key).suffix.lower(), "application/octet-stream")


class Storage(abc.ABC):
    """Common surface. ``workdir`` is where real files live locally."""

    workdir: Path

    def path_for(self, key: str) -> Path:
        p = (self.workdir / key.lstrip("/")).resolve()
        if self.workdir not in p.parents and p != self.workdir:
            raise ValueError(f"key escapes storage root: {key!r}")
        return p

    @abc.abstractmethod
    def ensure_local(self, key: str) -> Path: ...

    @abc.abstractmethod
    def persist(self, key: str) -> None: ...

    @abc.abstractmethod
    def write_bytes(self, key: str, data: bytes) -> str: ...

    @abc.abstractmethod
    def read_bytes(self, key: str) -> bytes: ...

    @abc.abstractmethod
    def exists(self, key: str) -> bool: ...

    @abc.abstractmethod
    def delete(self, key: str) -> None: ...

    @abc.abstractmethod
    def list(self, prefix: str) -> list[str]: ...

    @abc.abstractmethod
    def url_for(self, key: str) -> str: ...

    # --- convenience (identical for every backend) --------------------
    def write_text(self, key: str, text: str) -> str:
        return self.write_bytes(key, text.encode("utf-8"))

    def read_text(self, key: str) -> str:
        return self.read_bytes(key).decode("utf-8")

    def save_wav(self, key: str, x: np.ndarray, sr: int = dsp.SR) -> str:
        dsp.save_wav(self.path_for(key), x, sr)
        self.persist(key)
        return key

    def read_stereo(self, key: str, sr: int = dsp.SR) -> np.ndarray:
        return dsp.load_stereo(self.ensure_local(key), sr)

    def copy_in(self, src: Path, key: str) -> str:
        dst = self.path_for(key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        self.persist(key)
        return key


class LocalStorage(Storage):
    """Filesystem-backed store rooted at ``SR_STORAGE_ROOT``."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or get_settings().resolved_storage_root()).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.workdir = self.root

    def ensure_local(self, key: str) -> Path:
        return self.path_for(key)

    def persist(self, key: str) -> None:
        return None

    def write_bytes(self, key: str, data: bytes) -> str:
        p = self.path_for(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return key

    def read_bytes(self, key: str) -> bytes:
        return self.path_for(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self.path_for(key).exists()

    def delete(self, key: str) -> None:
        self.path_for(key).unlink(missing_ok=True)

    def list(self, prefix: str) -> list[str]:
        base = self.path_for(prefix) if prefix else self.root
        root = base if base.is_dir() else base.parent
        if not root.exists():
            return []
        out = []
        for p in root.rglob("*"):
            if p.is_file():
                rel = p.relative_to(self.root).as_posix()
                if rel.startswith(prefix):
                    out.append(rel)
        return sorted(out)

    def url_for(self, key: str) -> str:
        return f"file://{self.path_for(key)}"


class S3Storage(Storage):
    """S3-compatible object store (Supabase Storage, AWS S3, MinIO, …).

    Real files land in an ephemeral scratch dir and are uploaded on ``persist``;
    reads pull the object into scratch on first use.
    """

    def __init__(self) -> None:
        import boto3
        from botocore.config import Config

        s = get_settings()
        if not (s.s3_endpoint_url and s.s3_bucket and s.s3_access_key_id):
            raise RuntimeError(
                "SR_STORAGE_BACKEND=s3 needs SR_S3_ENDPOINT_URL, SR_S3_BUCKET, "
                "SR_S3_ACCESS_KEY_ID and SR_S3_SECRET_ACCESS_KEY"
            )
        self.bucket = s.s3_bucket
        self.workdir = Path(
            s.s3_workdir or (Path(tempfile.gettempdir()) / "sr-work")
        ).resolve()
        self.workdir.mkdir(parents=True, exist_ok=True)
        self._client = boto3.client(
            "s3",
            endpoint_url=s.s3_endpoint_url,
            region_name=s.s3_region or "us-east-1",
            aws_access_key_id=s.s3_access_key_id,
            aws_secret_access_key=s.s3_secret_access_key,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                # boto3 >= 1.36 adds CRC32 checksums with streaming trailers by
                # default; Supabase Storage (and most non-AWS S3) rejects those.
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )

    def ensure_local(self, key: str) -> Path:
        p = self.path_for(key)
        if p.exists():
            return p
        p.parent.mkdir(parents=True, exist_ok=True)
        self._client.download_file(self.bucket, key.lstrip("/"), str(p))
        return p

    def persist(self, key: str) -> None:
        with self.path_for(key).open("rb") as fh:
            self._client.put_object(
                Bucket=self.bucket, Key=key.lstrip("/"), Body=fh,
                ContentType=_content_type(key),
            )

    def write_bytes(self, key: str, data: bytes) -> str:
        p = self.path_for(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        self._client.put_object(
            Bucket=self.bucket, Key=key.lstrip("/"), Body=data,
            ContentType=_content_type(key),
        )
        return key

    def read_bytes(self, key: str) -> bytes:
        return self._client.get_object(Bucket=self.bucket, Key=key.lstrip("/"))["Body"].read()

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self._client.head_object(Bucket=self.bucket, Key=key.lstrip("/"))
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=key.lstrip("/"))
        self.path_for(key).unlink(missing_ok=True)

    def list(self, prefix: str) -> list[str]:
        keys: list[str] = []
        token: str | None = None
        while True:
            kw = {"Bucket": self.bucket, "Prefix": prefix.lstrip("/")}
            if token:
                kw["ContinuationToken"] = token
            resp = self._client.list_objects_v2(**kw)
            keys.extend(o["Key"] for o in resp.get("Contents", []))
            if not resp.get("IsTruncated"):
                break
            token = resp.get("NextContinuationToken")
        return sorted(keys)

    def url_for(self, key: str) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key.lstrip("/")},
            ExpiresIn=3600,
        )


_S3_SINGLETON: S3Storage | None = None


def get_storage() -> Storage:
    global _S3_SINGLETON
    if get_settings().storage_backend == "s3":
        if _S3_SINGLETON is None:
            _S3_SINGLETON = S3Storage()
        return _S3_SINGLETON
    return LocalStorage()


def reset_storage_cache() -> None:
    """Test hook - drop the memoized S3 client."""
    global _S3_SINGLETON
    _S3_SINGLETON = None
