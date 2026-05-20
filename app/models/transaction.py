from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, ForeignKey,
                        String, Text)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True)
    idempotency_key = Column(String, nullable=True, unique=True, index=True)
    entity_id = Column(String, ForeignKey("entities.id"), nullable=False)
    account_id = Column(String, nullable=True)

    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="USD")
    txn_type = Column(String)
    direction = Column(String)
    channel = Column(String)

    counterparty_name = Column(String, nullable=True)
    counterparty_account = Column(String, nullable=True)
    counterparty_bank = Column(String, nullable=True)
    counterparty_country = Column(String, nullable=True)

    merchant_name = Column(String, nullable=True)
    merchant_category = Column(String, nullable=True)
    location_city = Column(String, nullable=True)
    location_country = Column(String, nullable=True)

    risk_score = Column(Float, default=0.0)
    is_flagged = Column(Boolean, default=False)
    flag_reasons = Column(JSON, default=[])
    rule_hits = Column(JSON, default=[])
    ml_score = Column(Float, default=0.0)

    txn_timestamp = Column(DateTime, nullable=False)
    processed_at = Column(DateTime, server_default=func.now())
    notes = Column(Text, nullable=True)

    entity = relationship("Entity", back_populates="transactions")

    def __repr__(self):
        return f"<Transaction {self.id} - {self.txn_type} ${self.amount} [{self.entity_id}]>"
