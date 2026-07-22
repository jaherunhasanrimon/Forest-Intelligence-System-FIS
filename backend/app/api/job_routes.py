import os
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.job import Job
from app.models.analysis_result import AnalysisResult
from app.models.report import Report
from app.schemas.job import JobResponse, JobStatusDetail
from app.schemas.analysis import AnalysisResultResponse

router = APIRouter(prefix="/jobs", tags=["Monitoring Jobs"])


@router.get("", response_model=List[JobResponse])
def list_jobs(db: Session = Depends(get_db)):
    """
    Retrieve the list of all monitoring jobs.
    In Phase 2, this fetches runs submitted by the guest user.
    """
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


@router.get("/{job_id}/results", response_model=AnalysisResultResponse)
def get_job_results(job_id: int, db: Session = Depends(get_db)):
    """
    Retrieve computed AI analysis metrics (canopy %, tree count, biomass, carbon, health).
    """
    result = db.query(AnalysisResult).filter(AnalysisResult.job_id == job_id).first()
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis results for Job #{job_id} not available or processing incomplete."
        )
    return result


@router.get("/{job_id}/report/download")
def download_job_report(job_id: int, format: str = "pdf", db: Session = Depends(get_db)):
    """
    Download the generated executive report file (format='pdf' or format='html').
    """
    db_report = db.query(Report).filter(Report.job_id == job_id).first()
    if not db_report:
        # Check if local fallback file exists
        pdf_fallback = os.path.join("storage", "reports", f"job_{job_id}_report.pdf")
        html_fallback = os.path.join("storage", "reports", f"job_{job_id}_report.html")
        
        target_file = pdf_fallback if format == "pdf" else html_fallback
        if not os.path.exists(target_file):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report file for Job #{job_id} not found or generation in progress."
            )
    else:
        if format == "html":
            target_file = os.path.join("storage", "reports", f"job_{job_id}_report.html")
        else:
            target_file = db_report.file_path or os.path.join("storage", "reports", f"job_{job_id}_report.pdf")

    if not os.path.exists(target_file):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requested report file '{target_file}' does not exist."
        )

    media_type = "application/pdf" if format == "pdf" else "text/html"
    filename = f"Forest_Intelligence_Report_Job_{job_id}.{format}"

    return FileResponse(
        path=target_file,
        media_type=media_type,
        filename=filename
    )


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
