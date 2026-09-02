"""Desktop build: one process serves the API under /api and the web UI at /."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from sr.api.main import create_app
from sr.config import get_settings


@pytest.fixture
def served_client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    out = tmp_path / "web"
    out.mkdir()
    (out / "index.html").write_text("<!doctype html><title>home</title>", encoding="utf-8")
    sub = out / "song"
    sub.mkdir()
    (sub / "index.html").write_text("<!doctype html><title>song</title>", encoding="utf-8")

    monkeypatch.setenv("SR_FRONTEND_DIR", str(out))
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as c:
            yield c
    finally:
        get_settings.cache_clear()


def test_api_moves_under_prefix(served_client: TestClient) -> None:
    assert served_client.get("/api/health").status_code == 200
    # the bare (cloud) path is now owned by the static mount, not the API
    assert served_client.get("/health").status_code == 404


def test_web_ui_is_served(served_client: TestClient) -> None:
    assert "home" in served_client.get("/").text
    # client-routed page resolves via html=True
    assert "song" in served_client.get("/song/").text


def test_missing_frontend_dir_is_fatal(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SR_FRONTEND_DIR", str(tmp_path / "does-not-exist"))
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="index.html"):
            create_app()
    finally:
        get_settings.cache_clear()
