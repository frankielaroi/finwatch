import uuid
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entity import Entity
from app.models.profile import Profile, ProfileAlias
from app.models.transaction import Transaction
from app.models.worker import ProfileDLQ


def generate_profile_id() -> str:
    uid = str(uuid.uuid4().int)[:8]
    return f"PRF-{uid.zfill(8)}"


async def get_profile(db: AsyncSession, profile_id: str) -> Profile | None:
    result = await db.execute(
        select(Profile)
        .where(Profile.id == profile_id)
        .options(selectinload(Profile.aliases_rel))
    )
    return result.scalar_one_or_none()


async def find_profiles_by_external(
    db: AsyncSession, service: str, external_id: str
) -> list[Profile]:
    q = (
        select(Profile)
        .join(ProfileAlias)
        .where(ProfileAlias.service == service, ProfileAlias.external_id == external_id)
    )
    result = await db.execute(q)
    return result.scalars().all()


async def find_profiles_by_entity_contacts(
    db: AsyncSession, emails: list[str] | None, phones: list[str] | None
) -> list[Profile]:
    # Simple heuristic: find entities with matching emails/phones, then profiles linked to those entities
    if not emails and not phones:
        return []

    # Fetch candidate entities and perform overlap testing in Python to avoid DB JSON operators
    q = select(Entity).where(Entity.is_active is True)
    res = await db.execute(q)
    entities = res.scalars().all()
    matched_entity_ids: list[str] = []
    email_set = set((emails or []))
    phone_set = set((phones or []))
    for e in entities:
        e_emails = set(e.emails or [])
        e_phones = set(e.phones or [])
        if email_set and e_emails.intersection(email_set):
            matched_entity_ids.append(e.id)
            continue
        if phone_set and e_phones.intersection(phone_set):
            matched_entity_ids.append(e.id)

    if not matched_entity_ids:
        return []

    q2 = select(Profile).where(Profile.linked_entities is not None)
    res2 = await db.execute(q2)
    profiles = res2.scalars().all()

    # Filter profiles whose linked_entities intersect matched_entity_ids
    out: list[Profile] = []
    matched_set = set(matched_entity_ids)
    for p in profiles:
        if set(p.linked_entities or []).intersection(matched_set):
            out.append(p)
    return out


async def create_profile_from_entity(
    db: AsyncSession, entity_id: str, canonical_name: str | None = None
) -> Profile:
    profile = Profile(
        id=generate_profile_id(),
        canonical_name=canonical_name,
        aliases=[],
        linked_entities=[entity_id],
        linked_accounts=[],
        source_services={},
    )
    db.add(profile)
    await db.flush()

    # Create alias linking back to entity
    alias = ProfileAlias(
        profile_id=profile.id,
        service="local",
        external_id=entity_id,
        entity_id=entity_id,
        last_seen_at=datetime.utcnow(),
    )
    db.add(alias)
    await db.flush()
    await db.refresh(profile)
    return profile


async def link_entity_to_profile(
    db: AsyncSession,
    profile_id: str,
    entity_id: str,
    service: str = "local",
    external_id: str | None = None,
):
    profile = await get_profile(db, profile_id)
    if not profile:
        return None
    # add entity id to linked_entities if missing
    profile.linked_entities = list(set((profile.linked_entities or []) + [entity_id]))

    # idempotent: check for existing alias
    existing = None
    try:
        res = await db.execute(
            select(ProfileAlias).where(
                ProfileAlias.profile_id == profile.id,
                ProfileAlias.service == service,
                ProfileAlias.external_id == (external_id or entity_id),
            )
        )
        existing = res.scalar_one_or_none()
    except Exception:
        existing = None

    if not existing:
        alias = ProfileAlias(
            profile_id=profile.id,
            service=service,
            external_id=external_id or entity_id,
            entity_id=entity_id,
            last_seen_at=datetime.utcnow(),
        )
        db.add(alias)

    await db.flush()
    await db.refresh(profile)
    return profile


async def merge_profiles(
    db: AsyncSession, target_profile_id: str, other_profile_id: str
) -> Profile | None:
    if target_profile_id == other_profile_id:
        return await get_profile(db, target_profile_id)

    target = await get_profile(db, target_profile_id)
    other = await get_profile(db, other_profile_id)
    if not target or not other:
        return None

    # Merge aliases and linked entities/accounts
    target.aliases = list(set((target.aliases or []) + (other.aliases or [])))
    target.linked_entities = list(
        set((target.linked_entities or []) + (other.linked_entities or []))
    )
    target.linked_accounts = list(
        set((target.linked_accounts or []) + (other.linked_accounts or []))
    )

    # Move aliases rows
    for a in other.aliases_rel:
        a.profile_id = target.id

    # Delete other profile record
    await db.flush()
    await db.execute(update(Profile).where(Profile.id == other.id).values(id=other.id))
    # Actually delete the other
    await db.delete(other)
    await db.flush()
    await db.refresh(target)
    return target


async def process_dlq_item(db: AsyncSession, dlq: ProfileDLQ) -> bool:
    """Attempt to reprocess a DLQ item. Returns True on success, False on permanent failure."""
    try:
        if dlq.source == "match_transactions":
            payload = dlq.payload or {}
            txn_id = payload.get("txn_id")
            if not txn_id:
                return False
            # fetch transaction
            res = await db.execute(select(Transaction).where(Transaction.id == txn_id))
            txn = res.scalar_one_or_none()
            if not txn:
                return False
            # get entity
            if not txn.entity_id:
                return False
            res = await db.execute(select(Entity).where(Entity.id == txn.entity_id))
            ent = res.scalar_one_or_none()
            if not ent:
                return False

            # find or create profile and link
            profiles = await find_profiles_by_entity_contacts(
                db, ent.emails or [], ent.phones or []
            )
            if not profiles:
                await create_profile_from_entity(
                    db, ent.id, canonical_name=ent.full_name
                )
            else:
                p = profiles[0]
                if ent.id not in (p.linked_entities or []):
                    await link_entity_to_profile(db, p.id, ent.id)

            # on success delete DLQ row
            await db.execute(delete(ProfileDLQ).where(ProfileDLQ.id == dlq.id))
            await db.flush()
            return True
        # unknown source -> cannot process here
        return False
    except Exception:
        return False
