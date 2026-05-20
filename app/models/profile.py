from sqlalchemy import (JSON, Column, DateTime, Float, ForeignKey, Integer,
                        String)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(String, primary_key=True)
    canonical_name = Column(String, nullable=True)
    aliases = Column(JSON, default=[])
    linked_entities = Column(JSON, default=[])  # list of entity ids
    linked_accounts = Column(JSON, default=[])

    source_services = Column(JSON, default={})

    risk_score = Column(Float, default=0.0)
    risk_tier = Column(String, default="LOW")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    aliases_rel = relationship(
        "ProfileAlias", back_populates="profile", cascade="all, delete"
    )

    def __repr__(self):
        return f"<Profile {self.id} - {self.canonical_name} [{self.risk_tier}]>"


class ProfileAlias(Base):
    __tablename__ = "profile_aliases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(String, ForeignKey("profiles.id"), nullable=False)
    service = Column(String, nullable=False)
    external_id = Column(String, nullable=False)
    entity_id = Column(String, ForeignKey("entities.id"), nullable=True)
    last_seen_at = Column(DateTime, nullable=True)

    profile = relationship("Profile", back_populates="aliases_rel")

    def __repr__(self):
        return f"<ProfileAlias {self.service}:{self.external_id} -> {self.profile_id}>"
