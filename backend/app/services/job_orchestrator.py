from datetime import datetime
import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.models.job import Job

logger = logging.getLogger(__name__)


def create_job(db: Session, aoi_id: int, user_id: int, start_date: datetime.date, end_date: datetime.date) -> Job:
    """
    Create a new stateful Job tracker in the database in PENDING status.
    """
    db_job = Job(
        aoi_id=aoi_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        status="PENDING"
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    logger.info("Job %d created for AOI %d in status PENDING.", db_job.id, aoi_id)
    return db_job


def update_job_status(db: Session, job_id: int, status: str, error_message: Optional[str] = None) -> Optional[Job]:
    """
    Update the status of a job and update the timestamps.
    Automatically sets completed_at if status enters a terminal state (COMPLETED, FAILED).
    """
    db_job = db.query(Job).filter(Job.id == job_id).first()
    if not db_job:
        logger.error("Attempted to update non-existent Job %d.", job_id)
        return None

    old_status = db_job.status
    db_job.status = status
    db_job.updated_at = datetime.utcnow()

    if error_message:
        db_job.error_message = error_message
        logger.warning("Job %d status update to %s with error: %s", job_id, status, error_message)
    else:
        logger.info("Job %d transitioning status: %s -> %s", job_id, old_status, status)

    # Set completed_at timestamp for terminal states
    if status in ["COMPLETED", "FAILED"]:
        db_job.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(db_job)
    return db_job
