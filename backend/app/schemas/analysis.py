from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class AnalysisResultResponse(BaseModel):
    id: int
    job_id: int
    forest_cover_pct: Optional[float] = None
    tree_count: Optional[int] = None
    biomass_tons: Optional[float] = None
    carbon_tons: Optional[float] = None
    co2_equivalent_tons: Optional[float] = None
    health_index: Optional[float] = None
    health_category: Optional[str] = None
    suitability_score: Optional[float] = None
    forest_loss_ha: Optional[float] = None
    forest_gain_ha: Optional[float] = None
    result_layers: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)
