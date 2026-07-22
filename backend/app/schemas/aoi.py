from datetime import date
from typing import List, Literal, Tuple, Optional
from pydantic import BaseModel, Field


class PolygonGeometry(BaseModel):
    type: Literal["Polygon"]
    # GeoJSON coordinates format: List of LinearRings, where each ring is a list of [lng, lat] coordinate pairs.
    coordinates: List[List[Tuple[float, float]]]


class AOICreate(BaseModel):
    name: str = Field(default="Amazon Sector G4", max_length=120)
    start_date: date
    end_date: date
    geometry: PolygonGeometry


class AOIResponse(BaseModel):
    id: int
    name: Optional[str]
    area_hectares: Optional[float]
    geometry: dict

    class Config:
        from_attributes = True


class JobSubmissionResponse(BaseModel):
    job_id: int
    status: str
    aoi_id: int
