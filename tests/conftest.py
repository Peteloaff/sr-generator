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
