"""Execute one GenerationJob by id.

Shared by every queue backend: eager, inline-thread, and RQ all ultimately call
``run_job(job_id)``. Captures status, timing, attempts, logs, error, and output
assets with lineage - the blueprint's "every job records everything" rule.

The lifecycle is three transactions so a failed render still records its
attempt count and error even though its own transaction is rolled back:
  1. mark running (attempts++)   2. run handler + persist results   3. on error, mark failed
"""

from __future__ import annotations

import traceback
from datetime import UTC, datetime

from sqlalchemy import func, select

from sr.db import session_scope
from sr.logging_conf import get_logger
from sr.models.audio_asset import AudioAsset
from sr.models.generation_job import GenerationJob
from sr.worker.handlers import get_handler

log = get_logger("worker.runner")

_TERMINAL = ("succeeded", "running")


def _begin(job_id: str) -> str | None:
    """Mark the job running. Returns None if it should not run."""
    with session_scope() as db:
        job = db.get(GenerationJob, job_id)
        if job is None:
            raise LookupError(f"job {job_id} not found")
        if job.status in _TERMINAL:
            log.warning("job %s already %s; skipping", job_id, job.status)
            return job.status
        job.status = "running"
        job.attempts += 1
        job.started_at = datetime.now(UTC)
        job.error = None
        job.progress = 0.0
        job.append_log(f"start attempt {job.attempts} job_type={job.job_type}")
    return None


def _mark_failed(job_id: str, error: str, tb: str) -> None:
    with session_scope() as db:
        job = db.get(GenerationJob, job_id)
        if job is None:
            return
        job.status = "failed"
        job.error = error
        job.append_log("ERROR\n" + tb)
        job.completed_at = datetime.now(UTC)


def run_job(job_id: str) -> str:
    skip = _begin(job_id)
    if skip is not None:
        return skip

    try:
        with session_scope() as db:
            job = db.get(GenerationJob, job_id)
            handler = get_handler(job.job_type)
            result = handler(job, db)
            # Handlers that build their own asset graph (render_section) return an
            # empty outputs list; simple providers return file specs.
            for spec in result.outputs:
                db.add(
                    AudioAsset(
                        song_id=job.song_id,
                        section_id=job.section_id,
                        generation_job_id=job.id,
                        parent_asset_id=(job.input_asset_ids or [None])[0]
                        if job.input_asset_ids
                        else None,
                        asset_type=spec.get("asset_type", "other"),
                        file_path=spec["file_path"],
                        sample_rate=spec.get("sample_rate"),
                        channels=spec.get("channels"),
                        duration=spec.get("duration"),
                    )
                )
            job.provider = result.provider
            job.provider_version = result.provider_version
            for line in result.logs:
                job.append_log(line)
            db.flush()
            produced = len(result.outputs) or db.scalar(
                select(func.count())
                .select_from(AudioAsset)
                .where(AudioAsset.generation_job_id == job.id)
            )
            job.append_log(f"produced {produced} asset(s)")
            job.status = "succeeded"
            job.progress = 1.0
            job.completed_at = datetime.now(UTC)
        return "succeeded"
    except Exception as exc:  # noqa: BLE001 - jobs must fail safely, not crash the worker
        log.exception("job %s failed", job_id)
        _mark_failed(job_id, f"{type(exc).__name__}: {exc}", traceback.format_exc())
        return "failed"
