from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import alerts, entities, profiles, transactions
from app.core.auth import is_protected_path, validate_api_key
from app.core.config import settings
from app.core.redis import connect_redis, disconnect_redis
from app.db.session import AsyncSessionLocal
from app.metrics.prometheus import metrics_response
from app.ml.retrain_job import run_retrain
from app.services.audit_service import record_audit_event
from app.services.monitoring_service import get_metrics_snapshot


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_redis()
    print("✅ Redis connected")
    # start scheduler for periodic retrain
    try:
        scheduler = AsyncIOScheduler()
        # schedule retrain at 03:00 UTC daily
        scheduler.add_job(run_retrain, trigger="cron", hour="3", minute="0")
        scheduler.start()
        app.state.scheduler = scheduler
        print("✅ Scheduler started for retrain job")
    except Exception:
        print("⚠️ Scheduler failed to start")
    yield
    # shutdown scheduler
    try:
        sched = getattr(app.state, "scheduler", None)
        if sched:
            sched.shutdown(wait=False)
    except Exception:
        pass
    await disconnect_redis()


app = FastAPI(
    title=settings.APP_NAME,
    description="Financial Crime Detection Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_and_audit_middleware(request: Request, call_next):
    if not is_protected_path(request.url.path) or request.method == "OPTIONS":
        return await call_next(request)

    auth_error = None
    auth_context = None
    try:
        auth_context = validate_api_key(request)
        request.state.actor_id = auth_context.actor_id
        request.state.authenticated = auth_context.authenticated
    except Exception as exc:
        auth_error = exc

    if auth_error is not None:
        response = JSONResponse(status_code=401, content={"detail": "Invalid API key"})
        try:
            async with AsyncSessionLocal.begin() as db:
                await record_audit_event(
                    db,
                    actor_id=getattr(request.state, "actor_id", None),
                    action="auth_failed",
                    resource_type=request.url.path.split("/")[3]
                    if request.url.path.startswith("/api/v1/")
                    and len(request.url.path.split("/")) > 3
                    else None,
                    resource_id=None,
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    success=False,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    details={"reason": "invalid_api_key"},
                )
        except Exception:
            pass
        return response

    try:
        response = await call_next(request)
    except Exception:
        try:
            async with AsyncSessionLocal.begin() as db:
                await record_audit_event(
                    db,
                    actor_id=getattr(request.state, "actor_id", None),
                    action=f"http_{request.method.lower()}",
                    resource_type=request.url.path.split("/")[3]
                    if request.url.path.startswith("/api/v1/")
                    and len(request.url.path.split("/")) > 3
                    else None,
                    resource_id=None,
                    method=request.method,
                    path=request.url.path,
                    status_code=500,
                    success=False,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    details={
                        "query": dict(request.query_params),
                        "error": "unhandled_exception",
                    },
                )
        except Exception:
            pass
        raise
    try:
        resource_parts = [part for part in request.url.path.split("/") if part]
        resource_type = resource_parts[2] if len(resource_parts) >= 3 else None
        resource_id = (
            resource_parts[3]
            if len(resource_parts) >= 4 and not resource_parts[3].startswith("{")
            else None
        )
        async with AsyncSessionLocal.begin() as db:
            await record_audit_event(
                db,
                actor_id=getattr(request.state, "actor_id", None),
                action=f"http_{request.method.lower()}",
                resource_type=resource_type,
                resource_id=resource_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                success=response.status_code < 400,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                details={"query": dict(request.query_params)},
            )
    except Exception:
        pass
    return response


# Routers
app.include_router(entities.router, prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(profiles.router, prefix="/api/v1")
from app.api.routes.model_registry import router as model_registry_router

app.include_router(model_registry_router, prefix="/api/v1")


@app.get("/", tags=["System"])
def root():
    return {"system": settings.APP_NAME, "status": "online", "version": "1.0.0"}


@app.get("/health", tags=["System"])
async def health():
    from app.core.redis import redis_client

    redis_ok = False
    try:
        await redis_client.ping()
        redis_ok = True
    except Exception:
        pass
    return {
        "status": "healthy",
        "redis": "connected" if redis_ok else "disconnected",
        "database": "postgresql@localhost:5432",
    }


@app.get("/metrics", tags=["System"])
async def metrics():
    async with AsyncSessionLocal() as db:
        snapshot = await get_metrics_snapshot(db)
    return {
        "dlq_count": snapshot.dlq_count,
        "dlq_oldest_created_at": snapshot.dlq_oldest_created_at,
        "dlq_most_recent_attempt_at": snapshot.dlq_most_recent_attempt_at,
        "worker_runs_last_24h": snapshot.worker_runs_last_24h,
        "worker_failures_last_24h": snapshot.worker_failures_last_24h,
        "scoring_failures_last_24h": snapshot.scoring_failures_last_24h,
        "latest_worker_runs": snapshot.latest_worker_runs,
        "alerts": snapshot.alerts,
    }


@app.get("/metrics/prometheus", tags=["System"])
async def prometheus_metrics():
    return metrics_response()
