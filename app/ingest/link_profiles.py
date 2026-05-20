"""Ingestion helper to link entities and transactions into Profiles.

This script provides two main operations:
 - `bootstrap_profiles` : create a Profile per existing Entity if none exists and link via ProfileAlias (service='local').
 - `match_transactions` : for new transactions, attempt to find a Profile by matching emails/phones or external ids and link the transaction's entity to that Profile.

Usage:
    python -m app.ingest.link_profiles --bootstrap
    python -m app.ingest.link_profiles --match-transactions
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from typing import Optional

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.entity import Entity
from app.models.transaction import Transaction
from app.models.worker import ProcessingLog, ProfileDLQ, WorkerCheckpoint
from app.services import profile_service


async def bootstrap_profiles(limit: Optional[int] = None):
    async with AsyncSessionLocal() as db:  # type: AsyncSession
        q = select(Entity)
        if limit:
            q = q.limit(limit)
        res = await db.execute(q)
        entities = res.scalars().all()
        created = 0
        for e in entities:
            # check if there's already a profile linked
            profiles = await profile_service.find_profiles_by_entity_contacts(
                db, e.emails or [], e.phones or []
            )
            if profiles:
                # ensure this entity_id is included in profile.linked_entities
                for p in profiles:
                    if e.id not in (p.linked_entities or []):
                        await profile_service.link_entity_to_profile(db, p.id, e.id)
                continue
            # create new profile for this entity
            await profile_service.create_profile_from_entity(
                db, e.id, canonical_name=e.full_name
            )
            created += 1
        await db.commit()
        print(f"Bootstrapped {created} profiles")


async def match_transactions(limit: Optional[int] = None):
    async with AsyncSessionLocal() as db:
        # load last checkpoint
        res = await db.execute(
            select(WorkerCheckpoint).where(
                WorkerCheckpoint.key == "profiles_last_txn_at"
            )
        )
        cp = res.scalar_one_or_none()
        last_ts = None
        if cp and cp.value and cp.value.get("last_txn_at"):
            last_ts = cp.value.get("last_txn_at")

        q = select(Transaction).where(Transaction.is_flagged is True)
        if last_ts:
            q = q.where(Transaction.txn_timestamp > last_ts)
        q = q.order_by(Transaction.txn_timestamp.asc())
        if limit:
            q = q.limit(limit)
        res = await db.execute(q)
        txns = res.scalars().all()
        linked = 0
        max_ts = last_ts
        for t in txns:
            try:
                if not t.entity_id:
                    continue
                entity_q = select(Entity).where(Entity.id == t.entity_id)
                ent_res = await db.execute(entity_q)
                ent = ent_res.scalar_one_or_none()
                if not ent:
                    continue

                profiles = await profile_service.find_profiles_by_entity_contacts(
                    db, ent.emails or [], ent.phones or []
                )
                if not profiles:
                    p = await profile_service.create_profile_from_entity(
                        db, ent.id, canonical_name=ent.full_name
                    )
                    linked += 1
                else:
                    p = profiles[0]
                    if ent.id not in (p.linked_entities or []):
                        await profile_service.link_entity_to_profile(db, p.id, ent.id)
                        linked += 1

                # mark processed
                log = ProcessingLog(
                    txn_id=t.id, entity_id=t.entity_id, status="processed", details={}
                )
                db.add(log)
                if not max_ts or t.txn_timestamp > max_ts:
                    max_ts = t.txn_timestamp
            except Exception as exc:
                # push to DLQ
                dlq = ProfileDLQ(
                    source="match_transactions",
                    item_id=t.id,
                    payload={"txn_id": t.id},
                    error=str(exc),
                    attempts=1,
                    last_error_at=datetime.utcnow(),
                )
                db.add(dlq)
                log = ProcessingLog(
                    txn_id=t.id,
                    entity_id=t.entity_id if t else None,
                    status="failed",
                    details={"error": str(exc)},
                )
                db.add(log)

        # update checkpoint
        if max_ts:
            val = {"last_txn_at": max_ts.isoformat()}
            if cp:
                cp.value = val
            else:
                new = WorkerCheckpoint(key="profiles_last_txn_at", value=val)
                db.add(new)

        await db.commit()
        print(f"Linked {linked} entities to profiles based on transactions")


async def match_transactions(limit: Optional[int] = None):
    async with AsyncSessionLocal() as db:
        q = select(Transaction).where(Transaction.is_flagged is True)
        if limit:
            q = q.limit(limit)
        res = await db.execute(q)
        txns = res.scalars().all()
        linked = 0
        for t in txns:
            # find entity for the txn
            if not t.entity_id:
                continue
            entity_q = select(Entity).where(Entity.id == t.entity_id)
            ent_res = await db.execute(entity_q)
            ent = ent_res.scalar_one_or_none()
            if not ent:
                continue

            # try to find existing profiles by contact
            profiles = await profile_service.find_profiles_by_entity_contacts(
                db, ent.emails or [], ent.phones or []
            )
            if not profiles:
                # create a profile
                p = await profile_service.create_profile_from_entity(
                    db, ent.id, canonical_name=ent.full_name
                )
                linked += 1
            else:
                # link to first matching profile
                p = profiles[0]
                if ent.id not in (p.linked_entities or []):
                    await profile_service.link_entity_to_profile(db, p.id, ent.id)
                    linked += 1

        await db.commit()
        print(f"Linked {linked} entities to profiles based on transactions")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bootstrap", action="store_true")
    p.add_argument("--match-transactions", action="store_true")
    p.add_argument("--limit", type=int)
    args = p.parse_args()

    if args.bootstrap:
        asyncio.run(bootstrap_profiles(limit=args.limit))
    elif args.match_transactions:
        asyncio.run(match_transactions(limit=args.limit))
    else:
        p.print_help()


if __name__ == "__main__":
    main()
