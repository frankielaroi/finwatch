from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_registry import ModelVersion


async def register_model_version(
    db: AsyncSession,
    *,
    model_name: str,
    version: str,
    artifact_path: str,
    status: str = "candidate",
    metrics: dict[str, Any] | None = None,
    calibration: dict[str, Any] | None = None,
    training_data_hash: str | None = None,
    trained_at: datetime | None = None,
) -> ModelVersion:
    model = ModelVersion(
        model_name=model_name,
        version=version,
        artifact_path=artifact_path,
        status=status,
        is_active=False,
        metrics=metrics or {},
        calibration=calibration or {},
        training_data_hash=training_data_hash,
        trained_at=trained_at,
    )
    db.add(model)
    await db.flush()
    return model


async def get_active_model(db: AsyncSession, model_name: str) -> ModelVersion | None:
    result = await db.execute(
        select(ModelVersion).where(
            ModelVersion.model_name == model_name, ModelVersion.is_active is True
        )  # noqa: E712
    )
    return result.scalar_one_or_none()


async def promote_model(
    db: AsyncSession, model_name: str, version: str
) -> ModelVersion | None:
    result = await db.execute(
        select(ModelVersion).where(
            ModelVersion.model_name == model_name, ModelVersion.version == version
        )
    )
    model = result.scalar_one_or_none()
    if not model:
        return None

    await db.execute(
        update(ModelVersion)
        .where(ModelVersion.model_name == model_name)
        .values(is_active=False, status="candidate")
    )
    model.is_active = True
    model.status = "active"
    model.promoted_at = datetime.utcnow()
    model.rolled_back_at = None
    model.rollback_reason = None
    await db.flush()
    return model


async def rollback_model(
    db: AsyncSession, model_name: str, version: str, reason: str
) -> ModelVersion | None:
    result = await db.execute(
        select(ModelVersion).where(
            ModelVersion.model_name == model_name, ModelVersion.version == version
        )
    )
    model = result.scalar_one_or_none()
    if not model:
        return None
    model.is_active = False
    model.status = "rolled_back"
    model.rolled_back_at = datetime.utcnow()
    model.rollback_reason = reason
    await db.flush()
    return model


async def list_versions(
    db: AsyncSession, model_name: str | None = None
) -> list[ModelVersion]:
    q = select(ModelVersion)
    if model_name:
        q = q.where(ModelVersion.model_name == model_name)
    res = await db.execute(q.order_by(ModelVersion.created_at.desc()))
    return res.scalars().all()
