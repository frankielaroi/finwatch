from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.alert import Alert
from app.schemas.alert import AlertOut
from app.schemas.entity import (EntityCreate, EntityListItem, EntityOut,
                                EntityUpdate, RiskScores)
from app.services import entity_service

router = APIRouter(prefix="/entities", tags=["Entities"])


@router.post("/", response_model=EntityOut, status_code=201)
async def create_entity(data: EntityCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await entity_service.create_entity(db, data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=list[EntityListItem])
async def list_entities(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    risk_tier: Optional[str] = Query(None),
    kyc_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None, min_length=1),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await entity_service.get_entities(
            db, skip, limit, risk_tier, kyc_status, search
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{entity_id}", response_model=EntityOut)
async def get_entity(entity_id: str, db: AsyncSession = Depends(get_db)):
    entity = await entity_service.get_entity(db, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.put("/{entity_id}", response_model=EntityOut)
async def update_entity(
    entity_id: str, data: EntityUpdate, db: AsyncSession = Depends(get_db)
):
    entity = await entity_service.update_entity(db, entity_id, data)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.get("/{entity_id}/risk", response_model=RiskScores)
async def get_risk_scores(entity_id: str, db: AsyncSession = Depends(get_db)):
    entity = await entity_service.get_entity(db, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return RiskScores(
        risk_score=entity.risk_score,
        fraud_score=entity.fraud_score,
        aml_score=entity.aml_score,
        network_score=entity.network_score,
        risk_tier=entity.risk_tier,
        typology_matches=entity.typology_matches or [],
        last_anomaly_at=entity.last_anomaly_at,
    )


@router.get("/{entity_id}/alerts", response_model=list[AlertOut])
async def get_entity_alerts(entity_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Alert)
        .where(Alert.entity_id == entity_id)
        .order_by(Alert.created_at.desc())
    )
    return result.scalars().all()


@router.post("/{entity_id}/flag")
async def flag_entity(
    entity_id: str,
    reason: str = Query(..., description="Flag reason e.g. structuring"),
    db: AsyncSession = Depends(get_db),
):
    entity = await entity_service.flag_entity(db, entity_id, reason)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return {
        "message": f"Entity {entity_id} flagged",
        "reason": reason,
        "status": entity.kyc_status,
    }
