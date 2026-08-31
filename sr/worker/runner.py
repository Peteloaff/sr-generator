"""Execute one GenerationJob by id.

Shared by every queue backend: eager, inline-thread, and RQ all ultimately call
``run_job(job_id)``. Captures status, timing, attempts, logs, error, and output
assets with lineage - the blueprint's "every job records everything" rule.
"""

from __future__ import annotations

import traceback
from datetime import UTC, datetime

from sr.db import session_scope
from sr.logging_conf import get_logger
from sr.models.audio_asset import AudioAsset
from sr.models.generation_job import GenerationJob
from sr.worker.handlers import get_handler

log = get_logger("worker.runner")


def run_job(job_id: str) -> str:
    """Run the job, persist results, return the final status."""
    with session_scope() as db:
        job = db.get(GenerationJob, job_id)
        if job is None:
            raise LookupError(f"job {job_id} not found")
        if job.status in ("succeeded", "running"):
            log.warning("job %s already %s; skipping", job_id, job.status)
            return job.status

        job.status = "running"
        job.attempts += 1
        job.started_at = datetime.now(UTC)
        job.error = None
        job.progress = 0.0
        job.append_log(f"start attempt {job.attempts} job_type={job.job_type}")
        db.flush()

        try:
            handler = get_handler(job.job_type)
            result = handler(job)
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
            job.append_log(f"produced {len(result.outputs)} asset(s)")
            job.status = "succeeded"
            job.progress = 1.0
        except Exception as exc:  # noqa: BLE001 - jobs must fail safely, not crash the worker
            job.status = "failed"
            job.error = f"{type(exc).__name__}: {exc}"
            job.append_log("ERROR\n" + traceback.format_exc())
            log.exception("job %s failed", job_id)
        finally:
            job.completed_at = datetime.now(UTC)

        return job.status
