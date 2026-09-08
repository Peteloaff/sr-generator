"""Google Drive folder source (read-only).

No OAuth: share a Drive folder as "anyone with the link can view", set
``SR_GOOGLE_API_KEY``, and we list + download its audio through the public
Drive v3 REST API. Used to pull reference songs and player training material
from Drive instead of the local disk.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from sr.common.audio import SUPPORTED_SUFFIXES
from sr.config import get_settings

_API = "https://www.googleapis.com/drive/v3"
_FOLDER_MIME = "application/vnd.google-apps.folder"


class DriveError(RuntimeError):
    """Any failure talking to Drive (maps to HTTP 400/502 at the boundary)."""


def _api_key() -> str:
    key = get_settings().google_api_key
    if not key:
        raise DriveError(
            "Google Drive import needs an API key. Create one at "
            "console.cloud.google.com (APIs & Services -> Credentials) with the "
            "Drive API enabled, then set SR_GOOGLE_API_KEY."
        )
    return key


def parse_folder_id(url_or_id: str) -> str:
    s = (url_or_id or "").strip()
    for pat in (r"/folders/([A-Za-z0-9_-]+)", r"[?&]id=([A-Za-z0-9_-]+)"):
        m = re.search(pat, s)
        if m:
            return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{16,}", s):
        return s
    raise DriveError(f"could not find a Drive folder id in {url_or_id!r}")


def _get_json(path: str, params: dict) -> dict:
    q = urllib.parse.urlencode({**params, "key": _api_key()})
    req = urllib.request.Request(f"{_API}/{path}?{q}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed host
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read()[:300].decode("utf-8", "replace")
        raise DriveError(f"Drive API {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise DriveError(f"could not reach Drive: {exc.reason}") from exc


def list_folder_audio(folder_id: str, *, recursive: bool = True) -> list[dict]:
    """Return ``[{id, name, mimeType, size, path}]`` for audio files in the folder."""
    out: list[dict] = []
    stack: list[tuple[str, str]] = [(folder_id, "")]
    seen: set[str] = set()
    while stack:
        fid, prefix = stack.pop()
        if fid in seen:
            continue
        seen.add(fid)
        page: str | None = None
        while True:
            params = {
                "q": f"'{fid}' in parents and trashed=false",
                "fields": "nextPageToken,files(id,name,mimeType,size)",
                "pageSize": 1000,
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            }
            if page:
                params["pageToken"] = page
            data = _get_json("files", params)
            for f in data.get("files", []):
                if f["mimeType"] == _FOLDER_MIME:
                    if recursive:
                        stack.append((f["id"], f"{prefix}{f['name']}/"))
                elif Path(f["name"]).suffix.lower() in SUPPORTED_SUFFIXES:
                    out.append({**f, "path": f"{prefix}{f['name']}"})
            page = data.get("nextPageToken")
            if not page:
                break
    out.sort(key=lambda f: f["path"])
    return out


def download(file_id: str) -> bytes:
    q = urllib.parse.urlencode(
        {"alt": "media", "key": _api_key(), "supportsAllDrives": "true"}
    )
    req = urllib.request.Request(f"{_API}/files/{file_id}?{q}")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:  # noqa: S310 - fixed host
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise DriveError(f"Drive download {exc.code} for {file_id}") from exc
