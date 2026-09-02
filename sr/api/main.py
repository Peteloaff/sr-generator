"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from sr import __version__
from sr.api.routers import (
    arranger,
    bands,
    compose,
    health,
    jobs,
    morph,
    music,
    presets,
    projects,
    references,
    regen,
    render,
    singers,
    song_edit,
    songs,
    vocal,
    voice_models,
)
from sr.bootstrap import ensure_default_band
from sr.config import get_settings
from sr.db import session_scope
from sr.logging_conf import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        with session_scope() as db:
            ensure_default_band(db)
    except Exception:  # noqa: BLE001 - migrations may not have run yet; not fatal
        pass
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="SR Generator API",
        version=__version__,
        summary="Private AI band music workstation",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_prefix = "/api" if settings.serve_frontend else ""
    for module in (
        health, bands, singers, voice_models, references, projects, songs,
        vocal, presets, render, song_edit, music, compose, regen, arranger,
        morph, jobs,
    ):
        app.include_router(module.router, prefix=api_prefix)

    @app.get(f"{api_prefix}/", tags=["meta"])
    def root() -> dict:
        return {"name": "SR Generator", "version": __version__, "docs": "/docs"}

    if settings.serve_frontend:
        _mount_frontend(app, Path(settings.frontend_dir))

    return app


def _mount_frontend(app: FastAPI, root: Path) -> None:
    """Serve the exported Next.js site (desktop build) from this process.

    Registered after the API routers so ``/api/**`` still wins. ``html=True``
    resolves ``/song`` -> ``song/index.html`` for the client-routed pages.
    """
    root = root.resolve()
    if not (root / "index.html").exists():
        raise RuntimeError(f"SR_FRONTEND_DIR has no index.html: {root}")
    app.mount("/", StaticFiles(directory=str(root), html=True), name="frontend")


app = create_app()
