from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.profile import LinkEntityRequest, ProfileCreate, ProfileOut
from app.services import entity_service, profile_service

router = APIRouter(prefix="/profiles", tags=["Profiles"])


@router.post("/", response_model=ProfileOut, status_code=201)
async def create_profile(data: ProfileCreate, db: AsyncSession = Depends(get_db)):
    entity = await entity_service.get_entity(db, data.entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    profile = await profile_service.create_profile_from_entity(
        db, data.entity_id, data.canonical_name
    )
    return profile


@router.get("/{profile_id}", response_model=ProfileOut)
async def get_profile(profile_id: str, db: AsyncSession = Depends(get_db)):
    profile = await profile_service.get_profile(db, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.post("/{profile_id}/link", response_model=ProfileOut)
async def link_entity(
    profile_id: str, body: LinkEntityRequest, db: AsyncSession = Depends(get_db)
):
    entity = await entity_service.get_entity(db, body.entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    prof = await profile_service.link_entity_to_profile(
        db, profile_id, body.entity_id, body.service, body.external_id
    )
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    return prof


@router.get("/search", response_model=list[ProfileOut])
async def search_profiles(
    email: str | None = Query(None),
    phone: str | None = Query(None),
    service: str | None = Query(None),
    external_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    if service and external_id:
        return await profile_service.find_profiles_by_external(db, service, external_id)
    emails = [email] if email else None
    phones = [phone] if phone else None
    return await profile_service.find_profiles_by_entity_contacts(db, emails, phones)


@router.post("/trigger")
async def trigger_profiling():
    """Trigger the profiling worker to run once immediately."""
    from app.tasks.profile_worker import trigger_once

    trigger_once()
    return {"status": "scheduled"}
