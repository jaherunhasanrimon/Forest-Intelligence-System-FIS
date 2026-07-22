from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.job import Job
from app.schemas.job import JobResponse, JobStatusDetail

router = APIRouter(prefix="/jobs", tags=["Monitoring Jobs"])


@router.get("", response_model=List[JobResponse])
def list_jobs(db: Session = Depends(get_db)):
    """
    Retrieve the list of all monitoring jobs.
    In Phase 2, this fetches runs submitted by the guest user.
    """
    # Sort by created_at descending (newest runs first)
    jobs = db.query(Job).order_by(Job.created_at.desc()).all()
    return jobs


@router.get("/{job_id}/status", response_model=JobStatusDetail)
def get_job_status(job_id: int, db: Session = Depends(get_db)):
    """
    Retrieve the current execution status, timestamp details,
    and elapsed time of a specific monitoring job.
    """
    db_job = db.query(Job).filter(Job.id == job_id).first()
    if not db_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Monitoring Job with ID {job_id} not found."
        )

    # Compute elapsed seconds
    end_time = db_job.completed_at or datetime.utcnow()
    elapsed = (end_time - db_job.created_at).total_seconds()

    return {
        "job_id": db_job.id,
        "status": db_job.status,
        "error_message": db_job.error_message,
        "created_at": db_job.created_at,
        "updated_at": db_job.updated_at,
        "completed_at": db_job.completed_at,
        "elapsed_seconds": round(elapsed, 1)
    }


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: int, db: Session = Depends(get_db)):
    """
    Cancel or delete a monitoring job and its logs.
    """
    db_job = db.query(Job).filter(Job.id == job_id).first()
    if not db_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Monitoring Job with ID {job_id} not found."
        )

    db.delete(db_job)
    db.commit()
    return None
