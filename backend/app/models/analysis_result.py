from datetime import datetime
from sqlalchemy import Column, DateTime, Decimal, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from app.db import Base


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    forest_cover_pct = Column(Decimal(5, 2), nullable=True)
    tree_count = Column(Integer, nullable=True)
    biomass_tons = Column(Decimal(12, 2), nullable=True)
    carbon_tons = Column(Decimal(12, 2), nullable=True)
    co2_equivalent_tons = Column(Decimal(12, 2), nullable=True)
    health_index = Column(Decimal(5, 2), nullable=True)
    health_category = Column(String(30), nullable=True)
    suitability_score = Column(Decimal(5, 2), nullable=True)
    forest_loss_ha = Column(Decimal(10, 2), nullable=True)
    forest_gain_ha = Column(Decimal(10, 2), nullable=True)
    result_layers = Column(JSON, nullable=True)  # JSON holding path references to layer masks / visual overlays
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    job = relationship("Job", back_populates="analysis_result")
