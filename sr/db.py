"""Database engine and session management.

Portable across SQLite (Stage 0 default) and PostgreSQL (blueprint target) - the
only difference is ``SR_DATABASE_URL``. SQLite gets the pragmas it needs to behave
like a real RDBMS (foreign keys on).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from sr.config import get_settings

_settings = get_settings()

_is_sqlite = _settings.database_url.startswith("sqlite")

engine: Engine = create_engine(
    _settings.database_url,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    # Postgres over a connection pooler (Supabase) + a service that scales to zero:
    # recycle idle connections and check them before use.
    **({} if _is_sqlite else {"pool_pre_ping": True, "pool_recycle": 1800}),
)


if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _):  # noqa: ANN001
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session for workers and scripts."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
