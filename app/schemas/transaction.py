from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, condecimal, constr, validator


class TransactionCreate(BaseModel):
    idempotency_key: Optional[str] = None
    entity_id: str
    account_id: Optional[str] = None
    amount: condecimal(gt=0)
    currency: constr(min_length=3, max_length=4) = "USD"
    txn_type: str
    direction: Literal["inbound", "outbound"]
    channel: Optional[str] = None
    counterparty_name: Optional[str] = None
    counterparty_account: Optional[str] = None
    counterparty_bank: Optional[str] = None
    counterparty_country: Optional[str] = None
    merchant_name: Optional[str] = None
    merchant_category: Optional[str] = None
    location_city: Optional[str] = None
    location_country: Optional[str] = None
    txn_timestamp: datetime
    notes: Optional[str] = None

    @validator("txn_timestamp")
    def not_in_future(cls, v: datetime) -> datetime:
        if v > datetime.utcnow():
            raise ValueError("txn_timestamp cannot be in the future")
        return v


class TransactionOut(BaseModel):
    id: str
    idempotency_key: Optional[str] = None
    entity_id: str
    amount: float
    currency: str
    txn_type: str
    direction: str
    channel: Optional[str]
    counterparty_name: Optional[str]
    counterparty_country: Optional[str]
    merchant_name: Optional[str]
    merchant_category: Optional[str]
    location_city: Optional[str]
    location_country: Optional[str]
    risk_score: float
    is_flagged: bool
    flag_reasons: List[str]
    rule_hits: List[str]
    ml_score: float
    txn_timestamp: datetime
    processed_at: datetime
    notes: Optional[str]

    class Config:
        from_attributes = True
