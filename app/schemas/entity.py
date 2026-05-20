from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class RiskTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class KYCStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    SUSPENDED = "SUSPENDED"


# --- Document schemas ---
class DocumentBase(BaseModel):
    doc_type: str
    issuing_country: str
    issuing_state: Optional[str] = None
    expiry_date: Optional[date] = None
    is_verified: bool = False


class DocumentCreate(DocumentBase):
    doc_number_hash: str


class DocumentOut(DocumentBase):
    id: int
    entity_id: str
    verified_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Entity schemas ---
class EntityCreate(BaseModel):
    full_name: str
    aliases: Optional[List[str]] = Field(default_factory=list)
    date_of_birth: Optional[date] = None
    nationality: Optional[str] = None
    occupation: Optional[str] = None
    employer: Optional[str] = None
    phones: Optional[List[str]] = Field(default_factory=list)
    emails: Optional[List[str]] = Field(default_factory=list)
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    kyc_level: Optional[str] = "STANDARD"
    expected_monthly_inflow: Optional[float] = 0.0
    expected_monthly_outflow: Optional[float] = 0.0

    @validator("full_name")
    def name_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("full_name must be provided")
        return v.strip()


class EntityUpdate(BaseModel):
    full_name: Optional[str] = None
    aliases: Optional[List[str]] = None
    occupation: Optional[str] = None
    employer: Optional[str] = None
    phones: Optional[List[str]] = None
    emails: Optional[List[str]] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    kyc_status: Optional[KYCStatus] = None
    kyc_level: Optional[str] = None
    income_verified: Optional[bool] = None
    source_of_wealth_verified: Optional[bool] = None
    edd_required: Optional[bool] = None
    expected_monthly_inflow: Optional[float] = None
    expected_monthly_outflow: Optional[float] = None
    is_pep: Optional[bool] = None


class RiskScores(BaseModel):
    risk_score: float
    fraud_score: float
    aml_score: float
    network_score: float
    risk_tier: RiskTier
    typology_matches: List[str]
    last_anomaly_at: Optional[datetime]


class EntityOut(BaseModel):
    id: str
    full_name: str
    aliases: List[str]
    date_of_birth: Optional[date]
    nationality: Optional[str]
    occupation: Optional[str]
    employer: Optional[str]
    phones: List[str]
    emails: List[str]
    address: Optional[str]
    city: Optional[str]
    country: Optional[str]
    kyc_level: str
    kyc_status: str
    kyc_completed_at: Optional[datetime]
    kyc_next_review: Optional[datetime]
    income_verified: bool
    source_of_wealth_verified: bool
    edd_required: bool
    risk_score: float
    fraud_score: float
    aml_score: float
    network_score: float
    risk_tier: str
    aml_rating: str
    expected_monthly_inflow: float
    expected_monthly_outflow: float
    sars_filed: int
    typology_matches: List[str]
    is_pep: bool
    is_sanctioned: bool
    adverse_media_hits: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    documents: List[DocumentOut] = []

    class Config:
        from_attributes = True


class EntityListItem(BaseModel):
    id: str
    full_name: str
    risk_tier: str
    risk_score: float
    kyc_status: str
    aml_rating: str
    is_pep: bool
    is_sanctioned: bool
    typology_matches: List[str]
    created_at: datetime

    class Config:
        from_attributes = True
