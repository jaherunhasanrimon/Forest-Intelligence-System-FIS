from datetime import datetime
from sqlalchemy import Column, DateTime, Decimal, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from app.db import Base


class AOI(Base):
    __tablename__ = "aois"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(120), nullable=True)
    geometry = Column(JSON, nullable=False)  # GeoJSON representation
    area_hectares = Column(Decimal(10, 2), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="aois")
    jobs = relationship("Job", back_populates="aoi", cascade="all, delete-orphan")
