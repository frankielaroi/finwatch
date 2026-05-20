import enum

from sqlalchemy import (JSON, Boolean, Column, Date, DateTime, Float,
                        ForeignKey, Integer, String)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class RiskTier(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class KYCStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    SUSPENDED = "SUSPENDED"


class Entity(Base):
    __tablename__ = "entities"

    id = Column(String, primary_key=True)
    full_name = Column(String, nullable=False)
    aliases = Column(JSON, default=[])
    date_of_birth = Column(Date, nullable=True)
    nationality = Column(String(3))
    occupation = Column(String)
    employer = Column(String)

    phones = Column(JSON, default=[])
    emails = Column(JSON, default=[])
    address = Column(String)
    city = Column(String)
    country = Column(String)

    kyc_level = Column(String, default="STANDARD")
    kyc_status = Column(String, default=KYCStatus.PENDING)
    kyc_completed_at = Column(DateTime, nullable=True)
    kyc_next_review = Column(DateTime, nullable=True)
    income_verified = Column(Boolean, default=False)
    source_of_wealth_verified = Column(Boolean, default=False)
    edd_required = Column(Boolean, default=False)

    risk_score = Column(Float, default=0.0)
    fraud_score = Column(Float, default=0.0)
    aml_score = Column(Float, default=0.0)
    network_score = Column(Float, default=0.0)
    risk_tier = Column(String, default=RiskTier.LOW)

    aml_rating = Column(String, default="LOW")
    expected_monthly_inflow = Column(Float, default=0.0)
    expected_monthly_outflow = Column(Float, default=0.0)
    sars_filed = Column(Integer, default=0)
    typology_matches = Column(JSON, default=[])

    avg_transaction_amount = Column(Float, default=0.0)
    typical_hours = Column(String)
    typical_locations = Column(JSON, default=[])
    device_count = Column(Integer, default=0)
    last_anomaly_at = Column(DateTime, nullable=True)

    is_pep = Column(Boolean, default=False)
    is_sanctioned = Column(Boolean, default=False)
    adverse_media_hits = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    documents = relationship(
        "IdentityDocument", back_populates="entity", cascade="all, delete"
    )
    transactions = relationship(
        "Transaction", back_populates="entity", cascade="all, delete"
    )
    alerts = relationship("Alert", back_populates="entity", cascade="all, delete")

    def __repr__(self):
        return f"<Entity {self.id} - {self.full_name} [{self.risk_tier}]>"


class IdentityDocument(Base):
    __tablename__ = "identity_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(String, ForeignKey("entities.id"), nullable=False)
    doc_type = Column(String)
    doc_number_hash = Column(String)
    issuing_country = Column(String)
    issuing_state = Column(String, nullable=True)
    expiry_date = Column(Date, nullable=True)
    is_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    entity = relationship("Entity", back_populates="documents")
