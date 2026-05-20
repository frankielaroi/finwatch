from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.db.session import Base


class Case(Base):
    __tablename__ = "cases"

    id = Column(String, primary_key=True)
    entity_id = Column(String, nullable=False)
    alert_ids = Column(JSON, default=[])

    case_type = Column(String)
    status = Column(String, default="OPEN")
    priority = Column(Integer, default=3)
    title = Column(String)
    summary = Column(Text)

    assigned_to = Column(String, nullable=True)
    assigned_at = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)

    investigator_notes = Column(Text, nullable=True)
    evidence = Column(JSON, default=[])
    timeline = Column(JSON, default=[])

    sar_required = Column(Boolean, default=False)
    sar_drafted = Column(Boolean, default=False)
    sar_filed = Column(Boolean, default=False)
    sar_reference = Column(String, nullable=True)

    outcome = Column(String, nullable=True)
    closed_by = Column(String, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Case {self.id} - {self.case_type} [{self.status}]>"
