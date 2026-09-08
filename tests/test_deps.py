"""On-first-use install of the separation engine (behaviour, not the real install)."""

from __future__ import annotations

import sys

import pytest

from sr.common import deps


def test_deps_dir_is_added_to_path(monkeypatch, tmp_path):
    monkeypatch.setenv("SR_HOME", str(tmp_path))
    monkeypatch.setattr(deps, "demucs_available", lambda: True)
    deps.ensure_separation()
    assert str(tmp_path / "pydeps") in sys.path


def test_missing_and_no_auto_install_is_a_clear_error(monkeypatch, tmp_path):
    monkeypatch.setenv("SR_HOME", str(tmp_path))
    monkeypatch.delenv("SR_AUTO_INSTALL_SEPARATION", raising=False)
    monkeypatch.setattr(deps, "demucs_available", lambda: False)
    with pytest.raises(RuntimeError, match="separation"):
        deps.ensure_separation()


def test_auto_install_without_a_python_is_a_clear_error(monkeypatch, tmp_path):
    monkeypatch.setenv("SR_HOME", str(tmp_path))
    monkeypatch.setenv("SR_AUTO_INSTALL_SEPARATION", "1")
    monkeypatch.setattr(deps, "demucs_available", lambda: False)
    monkeypatch.setattr(deps, "_python", lambda: None)
    with pytest.raises(RuntimeError, match="system Python"):
        deps.ensure_separation()
