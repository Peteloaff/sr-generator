"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sr import __version__
from sr.api.routers import (
    bands,
    health,
    jobs,
    presets,
    projects,
    references,
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

    for module in (
        health, bands, singers, voice_models, references, projects, songs,
        vocal, presets, render, song_edit, jobs,
    ):
        app.include_router(module.router)

    @app.get("/", tags=["meta"])
    def root() -> dict:
        return {"name": "SR Generator", "version": __version__, "docs": "/docs"}

    return app


app = create_app()
