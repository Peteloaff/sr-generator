"""Desktop: an optional <SR_HOME>/.env lets a user supply their own overrides
(e.g. a personal Replicate token) without touching system environment
variables or baking anything into the .exe."""

from __future__ import annotations

import os

from sr.desktop import _load_user_env


def test_loads_env_file_when_present(tmp_path, monkeypatch):
    # load_dotenv mutates os.environ directly - monkeypatch.setenv/delenv only
    # reverts changes made *through* monkeypatch, so clean up by hand or these
    # values leak into every later test in the session.
    monkeypatch.delenv("SR_MUSIC_PROVIDER", raising=False)
    monkeypatch.delenv("SR_REPLICATE_API_TOKEN", raising=False)
    (tmp_path / ".env").write_text(
        "SR_MUSIC_PROVIDER=replicate\nSR_REPLICATE_API_TOKEN=my-own-token\n",
        encoding="utf-8",
    )
    try:
        _load_user_env(tmp_path)
        assert os.environ["SR_MUSIC_PROVIDER"] == "replicate"
        assert os.environ["SR_REPLICATE_API_TOKEN"] == "my-own-token"
    finally:
        os.environ.pop("SR_MUSIC_PROVIDER", None)
        os.environ.pop("SR_REPLICATE_API_TOKEN", None)


def test_no_env_file_is_a_silent_no_op(tmp_path, monkeypatch):
    monkeypatch.delenv("SR_MUSIC_PROVIDER", raising=False)
    _load_user_env(tmp_path)  # tmp_path/.env does not exist
    assert "SR_MUSIC_PROVIDER" not in os.environ
