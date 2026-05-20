from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def record_audit_event(
    db: AsyncSession,
    *,
    actor_id: str | None,
    action: str,
    resource_type: str | None,
    resource_id: str | None,
    method: str,
    path: str,
    status_code: int,
    success: bool,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        method=method,
        path=path,
        status_code=status_code,
        success=success,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
    )
    db.add(entry)
    await db.flush()
    return entry
