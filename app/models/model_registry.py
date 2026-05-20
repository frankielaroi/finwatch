from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.db.session import Base


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String, nullable=False, index=True)
    version = Column(String, nullable=False, unique=True, index=True)
    artifact_path = Column(String, nullable=False)
    status = Column(String, nullable=False, default="candidate", index=True)
    is_active = Column(Boolean, default=False, index=True)
    metrics = Column(JSON, nullable=True)
    calibration = Column(JSON, nullable=True)
    training_data_hash = Column(String, nullable=True, index=True)
    trained_at = Column(DateTime, nullable=True)
    promoted_at = Column(DateTime, nullable=True)
    rolled_back_at = Column(DateTime, nullable=True)
    rollback_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
