"""One-click desktop launcher.

Runs the entire SR Generator stack in a single local process: the FastAPI API,
the exported web UI served from the same origin, a SQLite database, and local
file storage - all under ``~/.sr-generator`` so it survives app updates.

This is the entry point PyInstaller freezes into ``SR Generator.exe`` (see
``scripts/build_desktop.ps1``). Running ``python -m sr.desktop`` from a checkout
does the same thing against ``apps/web/out`` if it has been built.

Environment is only ever set with ``setdefault`` - every knob can still be
overridden, which is what the test/dev overrides and the build script rely on.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _resource_root() -> Path:
    """Directory that holds bundled data (``alembic/``, ``web/``, ``sr/``)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]  # noqa: SLF001
    return Path(__file__).resolve().parent.parent


def _data_dir() -> Path:
    d = Path(os.environ.get("SR_HOME") or (Path.home() / ".sr-generator"))
    (d / "storage").mkdir(parents=True, exist_ok=True)
    return d


def _frontend_dir(res: Path) -> Path:
    # Frozen: datas land in <bundle>/web. Checkout: apps/web/out.
    for cand in (res / "web", res / "apps" / "web" / "out"):
        if (cand / "index.html").exists():
            return cand
    raise SystemExit(
        "web UI not found - build it first:\n"
        "  cd apps/web && STATIC_EXPORT=1 NEXT_PUBLIC_API_BASE=/api npm run build"
    )


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _configure_env() -> tuple[Path, Path]:
    res = _resource_root()
    data = _data_dir()
    os.environ.setdefault("SR_DATABASE_URL", f"sqlite:///{(data / 'sr.db').as_posix()}")
    os.environ.setdefault("SR_STORAGE_ROOT", str(data / "storage"))
    os.environ.setdefault("SR_STORAGE_BACKEND", "local")
    os.environ.setdefault("SR_QUEUE_BACKEND", "inline")
    os.environ.setdefault("SR_FRONTEND_DIR", str(_frontend_dir(res)))
    os.environ.setdefault("SR_API_CORS_ORIGINS", "http://127.0.0.1,http://localhost")
    return res, data


def _migrate(res: Path) -> None:
    from alembic.config import Config

    from alembic import command

    cfg = Config()
    cfg.set_main_option("script_location", str(res / "alembic"))
    # configparser reads '%' as interpolation; a SQLite path has none but keep
    # the escape so an overridden Postgres URL still works.
    cfg.set_main_option("sqlalchemy.url", os.environ["SR_DATABASE_URL"].replace("%", "%%"))
    command.upgrade(cfg, "head")


def _open_when_ready(url: str, port: int) -> None:
    for _ in range(200):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                break
        except OSError:
            time.sleep(0.1)
    webbrowser.open(url)


def main() -> None:
    res, data = _configure_env()
    print(f"SR Generator - data directory: {data}")
    _migrate(res)

    import uvicorn

    from sr.api.main import app

    port = int(os.environ.get("SR_PORT") or _free_port())
    url = f"http://127.0.0.1:{port}"
    threading.Thread(target=_open_when_ready, args=(url, port), daemon=True).start()
    print(f"SR Generator is running at {url}\nClose this window to stop it.")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
