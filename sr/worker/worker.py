"""RQ worker entrypoint (``sr-worker`` console script).

Only used when ``SR_QUEUE_BACKEND=rq``. On Windows RQ must use SimpleWorker
(no os.fork), which this selects automatically.
"""

from __future__ import annotations

import sys

from sr.config import get_settings
from sr.logging_conf import configure_logging, get_logger

log = get_logger("worker")


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)

    if settings.queue_backend != "rq":
        log.error(
            "SR_QUEUE_BACKEND=%s - the standalone worker is only for 'rq'. "
            "With 'inline' the API process runs jobs itself.",
            settings.queue_backend,
        )
        return 2

    from redis import Redis
    from rq import Queue, SimpleWorker

    conn = Redis.from_url(settings.redis_url)
    queue = Queue("sr", connection=conn)
    log.info("starting SimpleWorker on queue 'sr' (%s)", settings.redis_url)
    SimpleWorker([queue], connection=conn).work(with_scheduler=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
