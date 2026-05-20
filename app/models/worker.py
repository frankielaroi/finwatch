from sqlalchemy import JSON, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.db.session import Base


class WorkerCheckpoint(Base):
    __tablename__ = "worker_checkpoints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(JSON, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<WorkerCheckpoint {self.key}={self.value}>"


class ProfileDLQ(Base):
    __tablename__ = "profile_dlq"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, nullable=False)
    item_id = Column(String, nullable=True)
    payload = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    attempts = Column(Integer, default=0)
    last_error_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<ProfileDLQ {self.source}:{self.item_id} attempts={self.attempts}>"


class ProcessingLog(Base):
    __tablename__ = "profile_processing_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    txn_id = Column(String, nullable=True)
    entity_id = Column(String, nullable=True)
    status = Column(String, nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<ProcessingLog {self.txn_id or self.entity_id} {self.status}>"
