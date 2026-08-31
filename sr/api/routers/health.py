from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from sr import __version__
from sr.config import get_settings
from sr.db import engine
from sr.providers.registry import available
from sr.worker.handlers import known_job_types

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "version": __version__,
        "database_ok": db_ok,
        "queue_backend": settings.queue_backend,
        "providers": available(),
        "job_types": known_job_types(),
    }
