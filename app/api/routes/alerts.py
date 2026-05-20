from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.alert import Alert
from app.schemas.alert import AlertAssign, AlertOut, AlertResolve

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("/", response_model=list[AlertOut])
async def list_alerts(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    query = select(Alert)
    if status:
        query = query.where(Alert.status == status)
    if severity:
        query = query.where(Alert.severity == severity)
    query = query.order_by(Alert.priority.asc(), Alert.created_at.desc())
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{alert_id}", response_model=AlertOut)
async def get_alert(alert_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.put("/{alert_id}/assign")
async def assign_alert(
    alert_id: str, data: AlertAssign, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.assigned_to = data.assigned_to
    alert.assigned_at = datetime.utcnow()
    alert.status = "IN_REVIEW"
    return {"message": f"Alert {alert_id} assigned to {data.assigned_to}"}


@router.put("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str, data: AlertResolve, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.resolution = data.resolution
    alert.resolution_notes = data.resolution_notes
    alert.resolved_at = datetime.utcnow()
    alert.status = "CLOSED"
    if data.sar_required is not None:
        alert.sar_required = data.sar_required
    return {"message": f"Alert {alert_id} resolved", "resolution": data.resolution}
