import hashlib
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entity import Entity
from app.schemas.entity import EntityCreate, EntityUpdate


def generate_entity_id() -> str:
    uid = str(uuid.uuid4().int)[:8]
    return f"ENT-{uid.zfill(8)}"


def generate_doc_hash(doc_number: str) -> str:
    return hashlib.sha256(doc_number.encode()).hexdigest()


async def create_entity(db: AsyncSession, data: EntityCreate) -> Entity:
    entity = Entity(
        id=generate_entity_id(),
        full_name=data.full_name,
        aliases=data.aliases,
        date_of_birth=data.date_of_birth,
        nationality=data.nationality,
        occupation=data.occupation,
        employer=data.employer,
        phones=data.phones,
        emails=data.emails,
        address=data.address,
        city=data.city,
        country=data.country,
        kyc_level=data.kyc_level,
        kyc_status="PENDING",
        kyc_next_review=datetime.utcnow() + timedelta(days=365),
        expected_monthly_inflow=data.expected_monthly_inflow,
        expected_monthly_outflow=data.expected_monthly_outflow,
    )
    db.add(entity)
    await db.flush()
    await db.refresh(entity)
    # Reload entity with documents using selectinload so relationships are loaded
    result = await db.execute(
        select(Entity)
        .options(selectinload(Entity.documents))
        .where(Entity.id == entity.id)
    )
    loaded = result.scalar_one()
    return loaded


async def get_entity(db: AsyncSession, entity_id: str) -> Entity | None:
    result = await db.execute(
        select(Entity)
        .options(selectinload(Entity.documents))
        .where(Entity.id == entity_id)
    )
    return result.scalar_one_or_none()


async def get_entities(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    risk_tier: str = None,
    kyc_status: str = None,
    search: str = None,
) -> list[Entity]:
    query = select(Entity).where(Entity.is_active is True)

    if risk_tier:
        query = query.where(Entity.risk_tier == risk_tier)
    if kyc_status:
        query = query.where(Entity.kyc_status == kyc_status)
    if search:
        query = query.where(Entity.full_name.ilike(f"%{search}%"))

    query = query.order_by(Entity.risk_score.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def update_entity(
    db: AsyncSession, entity_id: str, data: EntityUpdate
) -> Entity | None:
    entity = await get_entity(db, entity_id)
    if not entity:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(entity, field, value)
    entity.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(entity)
    return entity


async def flag_entity(db: AsyncSession, entity_id: str, reason: str) -> Entity | None:
    entity = await get_entity(db, entity_id)
    if not entity:
        return None
    entity.kyc_status = "REVIEW_REQUIRED"
    entity.edd_required = True
    if reason not in (entity.typology_matches or []):
        entity.typology_matches = (entity.typology_matches or []) + [reason]
    entity.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(entity)
    return entity


async def update_risk_scores(
    db: AsyncSession,
    entity_id: str,
    risk_score: float,
    fraud_score: float,
    aml_score: float,
    network_score: float,
) -> Entity | None:
    entity = await get_entity(db, entity_id)
    if not entity:
        return None

    entity.risk_score = risk_score
    entity.fraud_score = fraud_score
    entity.aml_score = aml_score
    entity.network_score = network_score

    # Determine tier
    if risk_score >= 80:
        entity.risk_tier = "CRITICAL"
    elif risk_score >= 60:
        entity.risk_tier = "HIGH"
    elif risk_score >= 40:
        entity.risk_tier = "MEDIUM"
    else:
        entity.risk_tier = "LOW"

    entity.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(entity)
    return entity
