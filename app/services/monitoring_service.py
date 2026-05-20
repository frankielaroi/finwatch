from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.monitoring import ScoringFailure, WorkerRun
from app.models.worker import ProfileDLQ


@dataclass
class MetricsSnapshot:
    dlq_count: int
    dlq_oldest_created_at: str | None
    dlq_most_recent_attempt_at: str | None
    worker_runs_last_24h: int
    worker_failures_last_24h: int
    scoring_failures_last_24h: int
    latest_worker_runs: list[dict[str, Any]]
    alerts: list[dict[str, Any]]


async def record_worker_run(
    db: AsyncSession,
    *,
    worker_name: str,
    run_id: str,
    status: str,
    started_at: datetime,
    finished_at: datetime | None = None,
    duration_seconds: float | None = None,
    items_seen: int = 0,
    items_succeeded: int = 0,
    items_failed: int = 0,
    details: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> WorkerRun:
    run = WorkerRun(
        worker_name=worker_name,
        run_id=run_id,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=duration_seconds,
        items_seen=items_seen,
        items_succeeded=items_succeeded,
        items_failed=items_failed,
        details=details or {},
        error_message=error_message,
    )
    db.add(run)
    await db.flush()
    return run


async def record_scoring_failure(
    db: AsyncSession,
    *,
    transaction_id: str | None,
    entity_id: str | None,
    failure_reason: str,
    details: dict[str, Any] | None = None,
) -> ScoringFailure:
    failure = ScoringFailure(
        transaction_id=transaction_id,
        entity_id=entity_id,
        failure_reason=failure_reason,
        details=details or {},
    )
    db.add(failure)
    await db.flush()
    return failure


async def get_metrics_snapshot(db: AsyncSession) -> MetricsSnapshot:
    window_start = datetime.utcnow() - timedelta(
        minutes=int(settings.OPS_ALERT_WINDOW_MINUTES)
    )

    res_count = await db.execute(select(func.count(ProfileDLQ.id)))
    dlq_count = int(res_count.scalar() or 0)

    res_created = await db.execute(select(func.min(ProfileDLQ.created_at)))
    last_created = res_created.scalar()

    res_attempt = await db.execute(select(func.max(ProfileDLQ.last_error_at)))
    last_attempt = res_attempt.scalar()

    worker_runs_last_24h = await db.scalar(
        select(func.count(WorkerRun.id)).where(WorkerRun.started_at >= window_start)
    )
    worker_failures_last_24h = await db.scalar(
        select(func.count(WorkerRun.id)).where(
            WorkerRun.started_at >= window_start, WorkerRun.status == "failed"
        )
    )
    scoring_failures_last_24h = await db.scalar(
        select(func.count(ScoringFailure.id)).where(
            ScoringFailure.created_at >= window_start
        )
    )

    latest_runs = await db.execute(
        select(WorkerRun).order_by(WorkerRun.started_at.desc()).limit(5)
    )
    latest_worker_runs = [
        {
            "worker_name": run.worker_name,
            "run_id": run.run_id,
            "status": run.status,
            "started_at": None if not run.started_at else str(run.started_at),
            "finished_at": None if not run.finished_at else str(run.finished_at),
            "duration_seconds": run.duration_seconds,
            "items_seen": run.items_seen,
            "items_succeeded": run.items_succeeded,
            "items_failed": run.items_failed,
            "error_message": run.error_message,
        }
        for run in latest_runs.scalars().all()
    ]

    alerts: list[dict[str, Any]] = []
    if dlq_count >= int(settings.DLQ_ALERT_THRESHOLD):
        alerts.append(
            {
                "name": "dlq_backlog_high",
                "severity": "warning",
                "value": dlq_count,
                "threshold": int(settings.DLQ_ALERT_THRESHOLD),
            }
        )
    if int(worker_failures_last_24h or 0) >= int(
        settings.WORKER_FAILURE_ALERT_THRESHOLD
    ):
        alerts.append(
            {
                "name": "worker_failures_high",
                "severity": "critical",
                "value": int(worker_failures_last_24h or 0),
                "threshold": int(settings.WORKER_FAILURE_ALERT_THRESHOLD),
            }
        )
    if int(scoring_failures_last_24h or 0) >= int(
        settings.SCORING_FAILURE_ALERT_THRESHOLD
    ):
        alerts.append(
            {
                "name": "scoring_failures_high",
                "severity": "critical",
                "value": int(scoring_failures_last_24h or 0),
                "threshold": int(settings.SCORING_FAILURE_ALERT_THRESHOLD),
            }
        )

    return MetricsSnapshot(
        dlq_count=dlq_count,
        dlq_oldest_created_at=None if not last_created else str(last_created),
        dlq_most_recent_attempt_at=None if not last_attempt else str(last_attempt),
        worker_runs_last_24h=int(worker_runs_last_24h or 0),
        worker_failures_last_24h=int(worker_failures_last_24h or 0),
        scoring_failures_last_24h=int(scoring_failures_last_24h or 0),
        latest_worker_runs=latest_worker_runs,
        alerts=alerts,
    )
