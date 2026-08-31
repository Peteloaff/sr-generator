"""Test harness: isolated SQLite DB + storage per test session, eager job queue."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="sr-test-"))
os.environ["SR_DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["SR_STORAGE_ROOT"] = _TMP.as_posix()
os.environ["SR_QUEUE_BACKEND"] = "eager"
os.environ["SR_LOG_LEVEL"] = "WARNING"

from fastapi.testclient import TestClient  # noqa: E402

from sr.api.main import create_app  # noqa: E402
from sr.db import engine  # noqa: E402
from sr.models import Base  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema() -> Iterator[None]:
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.exec_driver_sql(f"DELETE FROM {table.name}")


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def sample_wav(tmp_path: Path) -> Path:
    """A short real WAV file for upload tests."""
    import numpy as np
    import soundfile as sf

    rate = 44100
    t = np.linspace(0, 1.5, int(rate * 1.5), endpoint=False)
    sig = (0.25 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    path = tmp_path / "clip.wav"
    sf.write(path, np.stack([sig, sig], axis=1), rate)
    return path


@pytest.fixture
def guide_wav(tmp_path: Path) -> Path:
    """A 3s pseudo-vocal 'melody' for guide-vocal / voice-conversion tests."""
    import numpy as np
    import soundfile as sf

    rate = 44100
    t = np.linspace(0, 3.0, int(rate * 3.0), endpoint=False)
    mel = np.zeros_like(t)
    for i, f in enumerate([180.0, 220.0, 200.0, 247.0, 180.0]):
        seg = (t >= i * 0.6) & (t < (i + 1) * 0.6)
        mel[seg] = np.sin(2 * np.pi * f * t[seg])
    am = 0.4 + 0.6 * np.clip(np.sin(2 * np.pi * 3 * t) ** 2, 0.0, 1.0)
    path = tmp_path / "guide.wav"
    sf.write(path, (0.4 * mel * am).astype(np.float32), rate)
    return path
