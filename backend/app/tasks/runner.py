"""Background task runner (threads) with cooperative cancellation.

Video jobs and async matching jobs run here. For production scale-out, swap
this for Celery/RQ/Arq — the job records in the database are the source of
truth for status/progress either way.
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, Dict

logger = logging.getLogger("mpis.tasks")

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mpis-job")
_futures: Dict[str, Future] = {}
_lock = threading.Lock()


def submit(job_id: str, fn: Callable[[], None]) -> None:
    def _run():
        try:
            fn()
        except Exception:
            logger.exception("job %s crashed", job_id)

    with _lock:
        _futures[job_id] = _executor.submit(_run)


def is_running(job_id: str) -> bool:
    with _lock:
        fut = _futures.get(job_id)
        return bool(fut and not fut.done())


def shutdown() -> None:
    _executor.shutdown(wait=False, cancel_futures=True)
