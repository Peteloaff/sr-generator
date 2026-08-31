"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sr import __version__
from sr.api.routers import health, jobs, projects, singers, songs
from sr.config import get_settings
from sr.logging_conf import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="SR Generator API",
        version=__version__,
        summary="Private AI band music workstation - Stage 0 foundation",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(singers.router)
    app.include_router(projects.router)
    app.include_router(songs.router)
    app.include_router(jobs.router)

    @app.get("/", tags=["meta"])
    def root() -> dict:
        return {"name": "SR Generator", "version": __version__, "docs": "/docs"}

    return app


app = create_app()
