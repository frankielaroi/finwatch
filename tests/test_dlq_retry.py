import sys
from pathlib import Path

import pytest

# skip test if aiosqlite not available in environment
pytest.importorskip("aiosqlite")

# ensure repo root on sys.path for test runner
sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.entity import Entity
from app.models.transaction import Transaction
from app.models.worker import ProcessingLog, ProfileDLQ
from app.tasks.dlq_retry_worker import run_dlq_once


@pytest.mark.asyncio
async def test_dlq_retry_processes_item(tmp_path):
    # setup in-memory sqlite async engine
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async with AsyncSessionLocal() as db:
        # create entity and transaction
        ent = Entity(
            id="ENT-TEST-1", full_name="Test User", emails=["t@test"], phones=["+100"]
        )
        db.add(ent)
        await db.flush()
        txn = Transaction(
            id="TXN-TEST-1",
            entity_id=ent.id,
            amount=1000.0,
            txn_timestamp="2026-01-01 00:00:00",
            is_flagged=True,
        )
        db.add(txn)
        await db.flush()

        # create DLQ entry referencing txn
        dlq = ProfileDLQ(
            source="match_transactions",
            item_id=txn.id,
            payload={"txn_id": txn.id},
            attempts=0,
        )
        db.add(dlq)
        await db.commit()

    # run dlq retry
    async with AsyncSessionLocal() as db:
        await run_dlq_once(batch_size=10, max_attempts=3)
        # verify DLQ cleared
        res = await db.execute(select(ProfileDLQ).where(ProfileDLQ.item_id == txn.id))
        remaining = res.scalars().all()
        assert len(remaining) == 0

        # verify a processing log exists
        res2 = await db.execute(
            select(ProcessingLog).where(ProcessingLog.txn_id == txn.id)
        )
        logs = res2.scalars().all()
        assert any(l.status == "dlq_processed" for l in logs)
