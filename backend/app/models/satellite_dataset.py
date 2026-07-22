from datetime import datetime
from sqlalchemy import Column, DateTime, DECIMAL, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db import Base


class SatelliteDataset(Base):
    __tablename__ = "satellite_datasets"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    gcs_uri = Column(String(255), nullable=True)
    local_path = Column(String(255), nullable=True)
    band_count = Column(Integer, default=10, nullable=False)
    resolution_m = Column(DECIMAL(5, 2), nullable=True)
    crs = Column(String(30), nullable=True)
    file_size_mb = Column(DECIMAL(10, 2), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    job = relationship("Job", back_populates="dataset")
