"""Report job progress from inside a long handler.

Writes on the handler's own session and flushes. On SQLite (single writer) a
separate transaction would deadlock against the open render transaction, so
progress becomes visible when the handler commits - which for the inline/eager
backends is the whole job anyway. On Postgres + RQ this still flushes promptly.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from sr.models.generation_job import GenerationJob


def report(db: Session, job: GenerationJob, fraction: float, note: str | None = None) -> None:
    frac = max(0.0, min(1.0, float(fraction)))
    job.progress = round(frac, 3)
    if note:
        job.append_log(f"[{int(frac * 100):3d}%] {note}")
    db.flush()
