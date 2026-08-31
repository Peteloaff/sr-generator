"""Storage abstraction. Local filesystem now; the interface is deliberately
S3-shaped (put/get/open/url by key) so an S3 backend drops in later.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from sr.config import get_settings


class LocalStorage:
    """Filesystem-backed object store rooted at ``SR_STORAGE_ROOT``."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or get_settings().resolved_storage_root()).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, key: str) -> Path:
        p = (self.root / key.lstrip("/")).resolve()
        if self.root not in p.parents and p != self.root:
            raise ValueError(f"key escapes storage root: {key!r}")
        return p

    def write_bytes(self, key: str, data: bytes) -> str:
        p = self.path_for(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return key

    def write_text(self, key: str, text: str) -> str:
        return self.write_bytes(key, text.encode("utf-8"))

    def read_bytes(self, key: str) -> bytes:
        return self.path_for(key).read_bytes()

    def copy_in(self, src: Path, key: str) -> str:
        p = self.path_for(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, p)
        return key

    def exists(self, key: str) -> bool:
        return self.path_for(key).exists()

    def url_for(self, key: str) -> str:
        return f"file://{self.path_for(key)}"


def get_storage() -> LocalStorage:
    return LocalStorage()
