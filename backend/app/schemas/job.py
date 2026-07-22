from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class JobResponse(BaseModel):
    id: int
    aoi_id: int
    user_id: int
    start_date: date
    end_date: date
    status: str
    gee_task_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobStatusDetail(BaseModel):
    job_id: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    elapsed_seconds: Optional[float] = None
