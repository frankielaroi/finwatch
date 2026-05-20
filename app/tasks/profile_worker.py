"""Production-ready background worker for profile ingestion/matching.

Features:
- Redis distributed lock to ensure a single runner across instances.
- Batching and per-run timeout to avoid long blocking operations.
- Structured logging and safe shutdown.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional


from app.core.config import settings
from app.core.redis import redis_client
from app.db.session import AsyncSessionLocal
from app.ingest.link_profiles import bootstrap_profiles, match_transactions
from app.metrics.prometheus import WORKER_RUN_FAILURES, WORKER_RUNS
from app.services.monitoring_service import record_worker_run

logger = logging.getLogger("finwatch.profile_worker")

_worker_task: Optional[asyncio.Task] = None
_stop_event: Optional[asyncio.Event] = None


def _lock_key() -> str:
    return "worker:profiles:lock"


async def _acquire_lock(owner_id: str, ttl: int) -> bool:
    # uses Redis SET NX EX
    if not redis_client:
        # no redis -> local only
        return True
    try:
        ok = await redis_client.set(_lock_key(), owner_id, nx=True, ex=ttl)
        return bool(ok)
    except Exception:
        logger.exception("redis lock acquire failed")
        return False


async def _release_lock(owner_id: str):
    if not redis_client:
        return
    try:
        val = await redis_client.get(_lock_key())
        if val == owner_id:
            await redis_client.delete(_lock_key())
    except Exception:
        logger.exception("redis lock release failed")


async def run_once(batch_size: Optional[int] = None, max_runtime: Optional[int] = None):
    owner_id = str(uuid.uuid4())
    lock_ttl = int(settings.PROFILE_WORKER_LOCK_TTL or 300)
    acquired = await _acquire_lock(owner_id, lock_ttl)
    if not acquired:
        logger.info("profile worker skipped: another instance holds lock")
        return

    started_at = datetime.utcnow()
    run_id = str(uuid.uuid4())
    status = "success"
    error_message = None
    details = {"batch_size": batch_size, "max_runtime": max_runtime}
    logger.info("profile worker acquired lock, running ingestion")
    try:
        coro = _run_ingest_cycle(batch_size)
        if max_runtime:
            await asyncio.wait_for(coro, timeout=max_runtime)
        else:
            await coro
    except asyncio.TimeoutError:
        logger.warning("profile worker run timed out after %s seconds", max_runtime)
        status = "timeout"
        error_message = "run timed out"
    except Exception:
        logger.exception("profile worker run failed")
        status = "failed"
        error_message = "run failed"
    finally:
        duration_seconds = (datetime.utcnow() - started_at).total_seconds()
        try:
            async with AsyncSessionLocal() as db:
                await record_worker_run(
                    db,
                    worker_name="profile",
                    run_id=run_id,
                    status=status,
                    started_at=started_at,
                    finished_at=datetime.utcnow(),
                    duration_seconds=duration_seconds,
                    items_seen=0,
                    items_succeeded=0,
                    items_failed=0,
                    details=details,
                    error_message=error_message,
                )
                await db.commit()
        except Exception:
            logger.exception("failed to persist profile worker run")
            WORKER_RUN_FAILURES.labels(worker="profile").inc()
        WORKER_RUNS.labels(worker="profile").inc()
        await _release_lock(owner_id)
        logger.info("profile worker released lock")


async def _run_ingest_cycle(batch_size: Optional[int] = None):
    # run bootstrap then matching with given batch size
    try:
        await bootstrap_profiles(limit=batch_size)
        await match_transactions(limit=batch_size)
    except Exception:
        logger.exception("error during ingest cycle")


async def _worker_loop(
    interval_seconds: int, batch_size: Optional[int], max_runtime: Optional[int]
):
    global _stop_event
    _stop_event = asyncio.Event()
    while not _stop_event.is_set():
        await run_once(batch_size=batch_size, max_runtime=max_runtime)
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue


def start_worker(
    interval_seconds: int = 300,
    batch_size: Optional[int] = None,
    max_runtime: Optional[int] = None,
):
    """Start the background worker; safe to call multiple times."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        logger.debug("profile worker already running")
        return
    loop = asyncio.get_event_loop()
    _worker_task = loop.create_task(
        _worker_loop(interval_seconds, batch_size, max_runtime)
    )


async def stop_worker():
    global _stop_event, _worker_task
    if _stop_event:
        _stop_event.set()
    if _worker_task:
        try:
            await _worker_task
        except Exception:
            logger.exception("error stopping worker task")
    _worker_task = None
    _stop_event = None


def trigger_once(batch_size: Optional[int] = None, max_runtime: Optional[int] = None):
    """Schedule a one-off run of the ingestion (non-blocking)."""
    loop = asyncio.get_event_loop()
    loop.create_task(run_once(batch_size=batch_size, max_runtime=max_runtime))
