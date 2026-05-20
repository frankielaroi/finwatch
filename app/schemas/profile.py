from typing import List, Optional

from pydantic import BaseModel


class ProfileAliasOut(BaseModel):
    service: str
    external_id: str
    entity_id: Optional[str]


class ProfileOut(BaseModel):
    id: str
    canonical_name: Optional[str]
    aliases: List[str] = []
    linked_entities: List[str] = []
    linked_accounts: List[str] = []
    risk_score: float = 0.0
    risk_tier: str = "LOW"

    class Config:
        orm_mode = True


class ProfileCreate(BaseModel):
    entity_id: str
    canonical_name: Optional[str]


class LinkEntityRequest(BaseModel):
    entity_id: str
    service: Optional[str] = "local"
    external_id: Optional[str]
