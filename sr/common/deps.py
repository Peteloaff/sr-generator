"""On-demand install of the heavy optional dependency (Demucs / torch).

The desktop build ships small: ``demucs`` (~2 GB with torch) is not bundled.
The first time real per-instrument separation is needed we install it into a
private directory under the data dir and add it to ``sys.path`` - so it "just
works" without bloating every build or every download.

Enabled by ``SR_AUTO_INSTALL_SEPARATION=1`` (set by ``sr/desktop.py``). Without
it, a missing ``demucs`` is a clear error and the user can switch to
``SR_MULTISTEM_PROVIDER=bandsplit``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_MARKER = "demucs"


def _deps_dir() -> Path:
    home = Path(os.environ.get("SR_HOME") or (Path.home() / ".sr-generator"))
    d = home / "pydeps"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _python() -> str | None:
    """A real Python interpreter we can run ``pip`` with."""
    if not getattr(sys, "frozen", False):
        return sys.executable
    import shutil

    for name in ("python", "python3", "py"):
        found = shutil.which(name)
        if found:
            return found
    return None


def demucs_available() -> bool:
    try:
        import demucs  # noqa: F401
        return True
    except ImportError:
        return False


def ensure_separation(*, on_log=None) -> None:
    """Import-or-install ``demucs``. Raises RuntimeError if it can't be made to work."""
    deps = _deps_dir()
    if str(deps) not in sys.path:
        sys.path.insert(0, str(deps))
    if demucs_available():
        return

    if os.environ.get("SR_AUTO_INSTALL_SEPARATION") != "1":
        raise RuntimeError(
            "Per-instrument separation needs Demucs. Install it with\n"
            '  pip install "sr-generator[separation]"\n'
            "or set SR_MULTISTEM_PROVIDER=bandsplit for the rough built-in split."
        )

    py = _python()
    if py is None:
        raise RuntimeError(
            "Demucs isn't installed and no system Python was found to install it. "
            "Install Python 3.12+, or set SR_MULTISTEM_PROVIDER=bandsplit."
        )

    def log(msg: str) -> None:
        (on_log or print)(msg)

    log("Installing the separation engine (Demucs + PyTorch, ~2 GB) — one time…")
    proc = subprocess.run(
        [py, "-m", "pip", "install", "--no-input", "--disable-pip-version-check",
         f"--target={deps}", "demucs>=4.0.1"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "could not install Demucs automatically:\n"
            + (proc.stderr or proc.stdout)[-800:]
            + "\nSet SR_MULTISTEM_PROVIDER=bandsplit to use the built-in split instead."
        )
    # importlib caches; make the freshly installed package discoverable
    import importlib
    import site

    site.addsitedir(str(deps))
    importlib.invalidate_caches()
    if not demucs_available():
        raise RuntimeError("Demucs installed but still not importable; restart the app.")
    log("Separation engine ready.")
