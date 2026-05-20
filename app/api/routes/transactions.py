from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.ml.scorer import score_transaction as score_txn
from app.schemas.transaction import TransactionCreate, TransactionOut
from app.services import entity_service, transaction_service

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("/", response_model=TransactionOut, status_code=201)
async def create_transaction(
    data: TransactionCreate, db: AsyncSession = Depends(get_db)
):
    # Verify entity exists
    try:
        entity = await entity_service.get_entity(db, data.entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        txn = await transaction_service.create_transaction(db, data, entity)
        return txn
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=list[TransactionOut])
async def list_transactions(
    entity_id: Optional[str] = Query(None),
    flagged_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await transaction_service.get_transactions(
            db, entity_id, flagged_only, skip, limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{txn_id}", response_model=TransactionOut)
async def get_transaction(txn_id: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select

    from app.models.transaction import Transaction

    result = await db.execute(select(Transaction).where(Transaction.id == txn_id))
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn


@router.post("/score", tags=["Transactions"])
async def score_transaction_endpoint(data: TransactionCreate):
    try:
        # support pydantic v2+ and v1
        if hasattr(data, "model_dump"):
            payload = data.model_dump()
        else:
            payload = data.dict()
        res = score_txn(payload)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
