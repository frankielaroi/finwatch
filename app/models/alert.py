from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, ForeignKey,
                        Integer, String, Text)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String, primary_key=True)
    entity_id = Column(String, ForeignKey("entities.id"), nullable=False)
    transaction_id = Column(String, nullable=True)

    alert_type = Column(String)
    typology = Column(String)
    severity = Column(String)
    risk_score = Column(Float)

    priority = Column(Integer, default=3)
    status = Column(String, default="OPEN")

    title = Column(String)
    description = Column(Text)
    evidence = Column(JSON, default=[])
    recommended_action = Column(String)
    # audit: who/what generated this alert ("scorer", "rules", "both")
    generated_by = Column(String, nullable=True)

    assigned_to = Column(String, nullable=True)
    assigned_at = Column(DateTime, nullable=True)

    resolved_by = Column(String, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution = Column(String, nullable=True)
    resolution_notes = Column(Text, nullable=True)

    sar_required = Column(Boolean, default=False)
    sar_filed = Column(Boolean, default=False)
    sar_filed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    entity = relationship("Entity", back_populates="alerts")

    def __repr__(self):
        return f"<Alert {self.id} - {self.typology} [{self.severity}] {self.status}>"
