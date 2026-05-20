import sys
from pathlib import Path

import pytest

pytest.importorskip("aiosqlite")
sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.alert import Alert
from app.models.entity import Entity
from app.services import transaction_service


@pytest.mark.asyncio
async def test_transaction_creates_alert(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async with AsyncSessionLocal() as db:
        ent = Entity(
            id="ENT-INT-1", full_name="Integration User", emails=["x@x"], phones=["+1"]
        )
        db.add(ent)
        await db.flush()

        from datetime import datetime

        txn_in = type(
            "T",
            (),
            {
                "idempotency_key": None,
                "entity_id": ent.id,
                "account_id": "ACCT-1",
                "amount": 15000.0,
                "currency": "USD",
                "txn_type": "cash_deposit",
                "direction": "inbound",
                "txn_timestamp": datetime.utcnow(),
                "counterparty_name": None,
                "counterparty_country": "IR",
                "notes": None,
            },
        )

        txn = await transaction_service.create_transaction(db, txn_in)
        assert txn is not None
        # confirm ml_score and alert created
        res = await db.execute(select(Alert).where(Alert.transaction_id == txn.id))
        alerts = res.scalars().all()
        assert len(alerts) >= 1

        # re-insert same idempotency should not create duplicate
        txn2 = await transaction_service.create_transaction(db, txn_in)
        assert txn2.id == txn.id
