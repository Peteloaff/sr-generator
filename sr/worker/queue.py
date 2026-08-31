"""Job queue abstraction.

Backends:
  * eager  - run synchronously on enqueue (tests, scripts)
  * inline - background thread pool, no Redis (Stage 0 native default)
  * rq     - Redis-backed RQ with SimpleWorker (blueprint target; needs Redis)

Call sites only ever see ``get_queue().enqueue(job_id)``.
"""

from __future__ import annotations

import abc
import time
from concurrent.futures import ThreadPoolExecutor

from sr.config import get_settings
from sr.db import SessionLocal
from sr.logging_conf import get_logger
from sr.models.generation_job import GenerationJob
from sr.worker.runner import run_job

log = get_logger("worker.queue")


class JobQueue(abc.ABC):
    backend: str = "base"

    @abc.abstractmethod
    def enqueue(self, job_id: str) -> str: ...

    def wait(self, job_id: str, timeout: float = 30.0, poll: float = 0.05) -> str:
        """Block until the job reaches a terminal state. Returns final status."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            db = SessionLocal()
            try:
                job = db.get(GenerationJob, job_id)
                if job and job.status in ("succeeded", "failed", "cancelled"):
                    return job.status
            finally:
                db.close()
            time.sleep(poll)
        raise TimeoutError(f"job {job_id} did not finish within {timeout}s")


class EagerJobQueue(JobQueue):
    backend = "eager"

    def enqueue(self, job_id: str) -> str:
        return run_job(job_id)

    def wait(self, job_id: str, timeout: float = 30.0, poll: float = 0.05) -> str:
        db = SessionLocal()
        try:
            job = db.get(GenerationJob, job_id)
            return job.status if job else "failed"
        finally:
            db.close()


class InlineThreadJobQueue(JobQueue):
    backend = "inline"
    _pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="sr-job")

    def enqueue(self, job_id: str) -> str:
        self._pool.submit(self._safe_run, job_id)
        log.info("enqueued %s (inline)", job_id)
        return "queued"

    @staticmethod
    def _safe_run(job_id: str) -> None:
        try:
            run_job(job_id)
        except Exception:  # noqa: BLE001
            log.exception("inline job %s crashed", job_id)


class RQJobQueue(JobQueue):
    backend = "rq"

    def __init__(self) -> None:
        from redis import Redis  # noqa: PLC0415
        from rq import Queue  # noqa: PLC0415

        self._q = Queue("sr", connection=Redis.from_url(get_settings().redis_url))

    def enqueue(self, job_id: str) -> str:
        self._q.enqueue("sr.worker.runner.run_job", job_id, job_timeout=3600)
        log.info("enqueued %s (rq)", job_id)
        return "queued"


_BACKENDS = {
    "eager": EagerJobQueue,
    "inline": InlineThreadJobQueue,
    "rq": RQJobQueue,
}

_queue: JobQueue | None = None


def get_queue() -> JobQueue:
    global _queue
    backend = get_settings().queue_backend
    if _queue is None or _queue.backend != backend:
        try:
            _queue = _BACKENDS[backend]()
        except KeyError as exc:
            raise KeyError(f"unknown queue backend {backend!r}") from exc
    return _queue


def reset_queue_cache() -> None:
    global _queue
    _queue = None
