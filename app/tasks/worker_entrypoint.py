from __future__ import annotations

import argparse
import asyncio
import signal
from typing import Optional

from app.core.config import settings
from app.tasks.dlq_retry_worker import run_dlq_once
from app.tasks.dlq_retry_worker import start_worker as start_dlq_worker
from app.tasks.dlq_retry_worker import stop_worker as stop_dlq_worker
from app.tasks.profile_worker import run_once as run_profile_once
from app.tasks.profile_worker import start_worker as start_profile_worker
from app.tasks.profile_worker import stop_worker as stop_profile_worker


def _install_stop_handler(stop_event: asyncio.Event) -> None:
    def _request_stop(*_args):
        stop_event.set()

    for sig_name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, _request_stop)
        except Exception:
            pass


async def run_profile_worker(
    once: bool = False,
    interval_seconds: Optional[int] = None,
    batch_size: Optional[int] = None,
    max_runtime: Optional[int] = None,
):
    if once:
        await run_profile_once(batch_size=batch_size, max_runtime=max_runtime)
        return

    stop_event = asyncio.Event()
    _install_stop_handler(stop_event)
    start_profile_worker(
        interval_seconds=int(
            interval_seconds or settings.PROFILE_WORKER_INTERVAL_SECONDS
        ),
        batch_size=int(batch_size or settings.PROFILE_WORKER_BATCH_SIZE),
        max_runtime=int(max_runtime or settings.PROFILE_WORKER_MAX_RUNTIME_SECONDS),
    )
    try:
        await stop_event.wait()
    finally:
        await stop_profile_worker()


async def run_dlq_worker(
    once: bool = False,
    interval_seconds: Optional[int] = None,
    batch_size: Optional[int] = None,
    max_attempts: Optional[int] = None,
):
    if once:
        await run_dlq_once(
            batch_size=int(batch_size or settings.PROFILE_DLQ_BATCH_SIZE),
            max_attempts=int(max_attempts or settings.PROFILE_DLQ_MAX_ATTEMPTS),
        )
        return

    stop_event = asyncio.Event()
    _install_stop_handler(stop_event)
    start_dlq_worker(
        interval_seconds=int(interval_seconds or settings.PROFILE_DLQ_INTERVAL_SECONDS),
        batch_size=int(batch_size or settings.PROFILE_DLQ_BATCH_SIZE),
        max_attempts=int(max_attempts or settings.PROFILE_DLQ_MAX_ATTEMPTS),
    )
    try:
        await stop_event.wait()
    finally:
        await stop_dlq_worker()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("worker", choices=["profile", "dlq"])
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--max-runtime", type=int, default=None)
    parser.add_argument("--max-attempts", type=int, default=None)
    return parser


def main(argv: Optional[list[str]] = None):
    args = _parser().parse_args(argv)
    if args.worker == "profile":
        asyncio.run(
            run_profile_worker(
                args.once, args.interval_seconds, args.batch_size, args.max_runtime
            )
        )
    else:
        asyncio.run(
            run_dlq_worker(
                args.once, args.interval_seconds, args.batch_size, args.max_attempts
            )
        )


if __name__ == "__main__":
    main()
