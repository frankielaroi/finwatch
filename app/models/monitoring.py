from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.sql import func

from app.db.session import Base


class WorkerRun(Base):
    __tablename__ = "worker_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    worker_name = Column(String, nullable=False, index=True)
    run_id = Column(String, nullable=False, unique=True, index=True)
    status = Column(String, nullable=False, index=True)
    started_at = Column(DateTime, nullable=False, server_default=func.now())
    finished_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    items_seen = Column(Integer, default=0)
    items_succeeded = Column(Integer, default=0)
    items_failed = Column(Integer, default=0)
    details = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)


class ScoringFailure(Base):
    __tablename__ = "scoring_failures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String, nullable=True, index=True)
    entity_id = Column(String, nullable=True, index=True)
    failure_reason = Column(String, nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)
