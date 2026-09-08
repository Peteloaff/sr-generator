"""Stage 17: Google Drive folder source (mocked HTTP)."""

from __future__ import annotations

import io
import wave

import numpy as np
import pytest

from sr.config import get_settings
from sr.services import drive


def _wav(seconds: float = 1.0, rate: int = 44100) -> bytes:
    t = np.linspace(0, seconds, int(seconds * rate), endpoint=False)
    pcm = (0.2 * np.sin(2 * np.pi * 220 * t) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


@pytest.fixture
def fake_drive(monkeypatch):
    tree = {
        "ROOT": [
            {"id": "f1", "name": "riff one.wav", "mimeType": "audio/wav"},
            {"id": "f2", "name": "notes.txt", "mimeType": "text/plain"},
            {"id": "sub", "name": "more", "mimeType": "application/vnd.google-apps.folder"},
        ],
        "sub": [{"id": "f3", "name": "solo.mp3", "mimeType": "audio/mpeg"}],
    }
    monkeypatch.setenv("SR_GOOGLE_API_KEY", "test-key")
    get_settings.cache_clear()

    def _get_json(path, params):
        fid = params["q"].split("'")[1]
        return {"files": tree.get(fid, [])}

    monkeypatch.setattr(drive, "_get_json", _get_json)
    monkeypatch.setattr(drive, "download", lambda fid: _wav())
    yield tree
    get_settings.cache_clear()


def test_parse_folder_id():
    assert drive.parse_folder_id(
        "https://drive.google.com/drive/folders/1AbC_def-123456789xyz"
    ) == "1AbC_def-123456789xyz"
    assert drive.parse_folder_id("1AbC_def-123456789xyz") == "1AbC_def-123456789xyz"
    with pytest.raises(drive.DriveError):
        drive.parse_folder_id("not a folder")


def test_list_folder_audio_recurses_and_filters(fake_drive):
    got = sorted(f["name"] for f in drive.list_folder_audio("ROOT", recursive=True))
    assert got == ["riff one.wav", "solo.mp3"]  # .txt skipped, subfolder walked
    shallow = drive.list_folder_audio("ROOT", recursive=False)
    assert [f["name"] for f in shallow] == ["riff one.wav"]


def test_missing_api_key_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("SR_GOOGLE_API_KEY", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(drive.DriveError, match="SR_GOOGLE_API_KEY"):
            drive.list_folder_audio("ROOT")
    finally:
        get_settings.cache_clear()


def test_import_drive_into_band_dna(client, fake_drive):
    band_id = client.get("/bands").json()[0]["id"]
    job = client.post(
        f"/bands/{band_id}/references/import-drive",
        json={"drive_folder": "https://drive.google.com/drive/folders/ROOT"},
    ).json()
    done = client.post(f"/jobs/{job['id']}/wait", params={"timeout": 60}).json()
    assert done["status"] == "succeeded", done.get("error")
    assert done["result_json"]["source"] == "drive"
    assert done["result_json"]["scanned"] == 2


def test_import_drive_player_samples(client, fake_drive):
    pid = client.post("/players", json={"name": "Dave", "role": "lead_guitar"}).json()["id"]
    made = client.post(
        f"/players/{pid}/samples/import-drive",
        json={"drive_folder": "https://drive.google.com/drive/folders/ROOT"},
    )
    assert made.status_code == 201
    assert len(made.json()) == 2
    assert len(client.get(f"/players/{pid}/samples").json()) == 2
