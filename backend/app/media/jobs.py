"""Minimal background job runner.

ffmpeg work runs in a small thread pool so API requests return immediately; the client polls the clip/reel
status. This is plenty for a single-user app. If it ever needs to survive restarts or run on another machine,
swap `submit` for a real queue (RQ, Celery, arq) without touching the pipeline functions.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor

from ..config import settings

log = logging.getLogger(__name__)
_pool: ThreadPoolExecutor | None = None


def _get_pool() -> ThreadPoolExecutor:
    global _pool
    if _pool is None:
        _pool = ThreadPoolExecutor(max_workers=settings.job_workers, thread_name_prefix="media")
    return _pool


def submit(fn: Callable, *args, **kwargs) -> Future | None:
    if settings.sync_jobs:
        fn(*args, **kwargs)
        return None
    fut = _get_pool().submit(fn, *args, **kwargs)
    fut.add_done_callback(lambda f: f.exception() and log.error("job %s failed", fn.__name__, exc_info=f.exception()))
    return fut


def shutdown(wait: bool = True) -> None:
    global _pool
    if _pool is not None:
        _pool.shutdown(wait=wait)
        _pool = None
