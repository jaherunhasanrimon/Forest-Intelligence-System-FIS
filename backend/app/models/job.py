from datetime import datetime
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    aoi_id = Column(Integer, ForeignKey("aois.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(String(20), default="PENDING", nullable=False)  # PENDING, EXPORTING, EXPORTED, DOWNLOADED, ANALYZING, COMPLETED, FAILED
    gee_task_id = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    aoi = relationship("AOI", back_populates="jobs")
    user = relationship("User", back_populates="jobs")
    dataset = relationship("SatelliteDataset", uselist=False, back_populates="job", cascade="all, delete-orphan")
    analysis_result = relationship("AnalysisResult", uselist=False, back_populates="job", cascade="all, delete-orphan")
    report = relationship("Report", uselist=False, back_populates="job", cascade="all, delete-orphan")
