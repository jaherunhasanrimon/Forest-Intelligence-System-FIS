from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    file_path = Column(String(255), nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    job = relationship("Job", back_populates="report")
