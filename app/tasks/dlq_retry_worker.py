"""DLQ retry worker: retries entries in `profile_dlq` and either resolves them or increments attempts.

Provides periodic worker with Redis locking, plus a programmatic trigger.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select, update

from app.core.config import settings
from app.core.redis import redis_client
from app.db.session import AsyncSessionLocal
from app.metrics.prometheus import (DLQ_CURRENT_SIZE, DLQ_ITEMS_FAILED,
                                    DLQ_ITEMS_SEEN, DLQ_ITEMS_SUCCEEDED,
                                    WORKER_RUN_FAILURES, WORKER_RUNS)
from app.models.worker import ProcessingLog, ProfileDLQ
from app.services import profile_service
from app.services.monitoring_service import record_worker_run

logger = logging.getLogger("finwatch.dlq_retry")

_worker_task: Optional[asyncio.Task] = None
_stop_event: Optional[asyncio.Event] = None


def _lock_key() -> str:
    return "worker:dlq:lock"


async def _acquire_lock(owner_id: str, ttl: int) -> bool:
    if not redis_client:
        return True
    try:
        ok = await redis_client.set(_lock_key(), owner_id, nx=True, ex=ttl)
        return bool(ok)
    except Exception:
        logger.exception("redis lock acquire failed for dlq")
        return False


async def _release_lock(owner_id: str):
    if not redis_client:
        return
    try:
        val = await redis_client.get(_lock_key())
        if val == owner_id:
            await redis_client.delete(_lock_key())
    except Exception:
        logger.exception("redis lock release failed for dlq")


async def run_dlq_once(batch_size: int = 100, max_attempts: int = 5):
    started_at = datetime.utcnow()
    run_id = str(uuid.uuid4())
    items_seen = 0
    items_succeeded = 0
    items_failed = 0
    status = "success"
    error_message = None
    async with AsyncSessionLocal() as db:  # type: AsyncSession
        q = select(ProfileDLQ).order_by(ProfileDLQ.created_at.asc()).limit(batch_size)
        res = await db.execute(q)
        items = res.scalars().all()
        items_seen = len(items)
        DLQ_CURRENT_SIZE.set(await db.scalar(select(func.count(ProfileDLQ.id))))
        for item in items:
            DLQ_ITEMS_SEEN.inc()
            if item.attempts >= max_attempts:
                logger.warning("DLQ item %s exceeded max attempts", item.id)
                await db.execute(
                    update(ProfileDLQ)
                    .where(ProfileDLQ.id == item.id)
                    .values(attempts=item.attempts + 1)
                )
                await db.flush()
                items_failed += 1
                continue
            try:
                ok = await profile_service.process_dlq_item(db, item)
                if ok:
                    logger.info("DLQ item %s processed successfully", item.id)
                    log = ProcessingLog(
                        txn_id=item.item_id,
                        entity_id=None,
                        status="dlq_processed",
                        details={},
                    )
                    db.add(log)
                    items_succeeded += 1
                    DLQ_ITEMS_SUCCEEDED.inc()
                else:
                    # increment attempts and record last_error_at
                    await db.execute(
                        update(ProfileDLQ)
                        .where(ProfileDLQ.id == item.id)
                        .values(
                            attempts=item.attempts + 1, last_error_at=datetime.utcnow()
                        )
                    )
                    logger.info(
                        "DLQ item %s processing failed, incremented attempts", item.id
                    )
                    items_failed += 1
                await db.flush()
            except Exception:
                logger.exception("unexpected error processing DLQ item %s", item.id)
                await db.execute(
                    update(ProfileDLQ)
                    .where(ProfileDLQ.id == item.id)
                    .values(attempts=item.attempts + 1, last_error_at=datetime.utcnow())
                )
                await db.flush()
                items_failed += 1
                DLQ_ITEMS_FAILED.inc()
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            await record_worker_run(
                db,
                worker_name="dlq",
                run_id=run_id,
                status=status,
                started_at=started_at,
                finished_at=datetime.utcnow(),
                duration_seconds=(datetime.utcnow() - started_at).total_seconds(),
                items_seen=items_seen,
                items_succeeded=items_succeeded,
                items_failed=items_failed,
                details={"batch_size": batch_size, "max_attempts": max_attempts},
                error_message=error_message,
            )
            await db.commit()
    except Exception:
        logger.exception("failed to persist dlq worker run")
    WORKER_RUN_FAILURES.labels(worker="dlq").inc()
    WORKER_RUNS.labels(worker="dlq").inc()


async def _run_once_with_lock(batch_size: int, max_attempts: int, lock_ttl: int):
    owner_id = str(uuid.uuid4())
    acquired = await _acquire_lock(owner_id, lock_ttl)
    if not acquired:
        logger.info("dlq retry skipped: another instance holds lock")
        return
    try:
        await run_dlq_once(batch_size=batch_size, max_attempts=max_attempts)
    finally:
        await _release_lock(owner_id)


async def _worker_loop(interval_seconds: int, batch_size: int, max_attempts: int):
    global _stop_event
    _stop_event = asyncio.Event()
    while not _stop_event.is_set():
        try:
            await _run_once_with_lock(
                batch_size=batch_size,
                max_attempts=max_attempts,
                lock_ttl=int(settings.PROFILE_WORKER_LOCK_TTL or 600),
            )
        except Exception:
            logger.exception("dlq worker run failed")
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue


def start_worker(
    interval_seconds: int = None, batch_size: int = None, max_attempts: int = None
):
    global _worker_task
    if _worker_task and not _worker_task.done():
        logger.debug("dlq worker already running")
        return
    loop = asyncio.get_event_loop()
    interval = int(interval_seconds or settings.PROFILE_DLQ_INTERVAL_SECONDS)
    bs = int(batch_size or settings.PROFILE_DLQ_BATCH_SIZE)
    ma = int(max_attempts or settings.PROFILE_DLQ_MAX_ATTEMPTS)
    _worker_task = loop.create_task(_worker_loop(interval, bs, ma))


async def stop_worker():
    global _stop_event, _worker_task
    if _stop_event:
        _stop_event.set()
    if _worker_task:
        try:
            await _worker_task
        except Exception:
            logger.exception("error stopping dlq worker task")
    _worker_task = None
    _stop_event = None


def trigger_dlq_retry(batch_size: int = None):
    loop = asyncio.get_event_loop()
    bs = int(batch_size or settings.PROFILE_DLQ_BATCH_SIZE)
    loop.create_task(
        _run_once_with_lock(
            batch_size=bs,
            max_attempts=int(settings.PROFILE_DLQ_MAX_ATTEMPTS),
            lock_ttl=int(settings.PROFILE_WORKER_LOCK_TTL),
        )
    )
