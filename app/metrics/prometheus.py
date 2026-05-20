from fastapi.responses import Response
from prometheus_client import (CONTENT_TYPE_LATEST, CollectorRegistry, Counter,
                               Gauge, generate_latest)

# registry and metrics
REGISTRY = CollectorRegistry()

# DLQ metrics
DLQ_ITEMS_SEEN = Counter(
    "finwatch_dlq_items_seen_total", "Total DLQ items seen", registry=REGISTRY
)
DLQ_ITEMS_SUCCEEDED = Counter(
    "finwatch_dlq_items_succeeded_total",
    "Total DLQ items processed successfully",
    registry=REGISTRY,
)
DLQ_ITEMS_FAILED = Counter(
    "finwatch_dlq_items_failed_total", "Total DLQ items failed", registry=REGISTRY
)
DLQ_CURRENT_SIZE = Gauge(
    "finwatch_dlq_current_size", "Current DLQ size", registry=REGISTRY
)

# Worker metrics
WORKER_RUNS = Counter(
    "finwatch_worker_runs_total", "Total worker runs", ["worker"], registry=REGISTRY
)
WORKER_RUN_FAILURES = Counter(
    "finwatch_worker_run_failures_total",
    "Total worker run failures",
    ["worker"],
    registry=REGISTRY,
)

# Scoring metrics
SCORING_FAILURES = Counter(
    "finwatch_scoring_failures_total", "Total scoring failures", registry=REGISTRY
)


def metrics_response() -> Response:
    data = generate_latest(REGISTRY)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
