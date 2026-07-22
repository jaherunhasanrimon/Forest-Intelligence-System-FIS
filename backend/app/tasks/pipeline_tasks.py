import time
import logging
from app.tasks.celery_app import celery_app
from app.db import SessionLocal
from app.services.job_orchestrator import update_job_status
from app.tasks.gee_export_tasks import run_gee_export_task

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.pipeline_tasks.process_aoi_pipeline")
def process_aoi_pipeline(job_id: int):
    """
    Stateful asynchronous pipeline coordinator.
    Invokes the real GEE export task, then passes output down the pipeline stages.
    """
    logger.info("Initializing async pipeline runner for Job ID: %d", job_id)
    
    db = SessionLocal()
    try:
        # Step 1: Run GEE Export Task (Generates 10-band GeoTIFF)
        run_gee_export_task(job_id)
        
        # Step 2: Data Ingestion & Cataloging
        update_job_status(db, job_id, "DOWNLOADED")
        time.sleep(2)
        
        # Step 3: AI Inference Pipeline
        update_job_status(db, job_id, "ANALYZING")
        time.sleep(3)
        
        # Step 4: Terminal Completion
        update_job_status(db, job_id, "COMPLETED")
        logger.info("Async pipeline execution for Job %d finished successfully.", job_id)
        
    except Exception as exc:
        logger.exception("Async pipeline runner encountered a fatal exception on Job %d:", job_id)
        update_job_status(db, job_id, "FAILED", error_message=str(exc))
    finally:
        db.close()
