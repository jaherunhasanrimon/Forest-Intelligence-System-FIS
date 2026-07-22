import time
import logging
from app.tasks.celery_app import celery_app
from app.db import SessionLocal
from app.services.job_orchestrator import update_job_status

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.pipeline_tasks.process_aoi_pipeline")
def process_aoi_pipeline(job_id: int):
    """
    Stateful asynchronous pipeline coordinator.
    Sequentially transitions the job status through all processing stages.
    
    This acts as a mockup pipeline with artificial delays to test the async queue,
    state persistence, and live frontend updates before real processing layers are wired.
    """
    logger.info("Initializing async pipeline runner for Job ID: %d", job_id)
    
    db = SessionLocal()
    try:
        # Step 1: Start GEE Export simulation
        update_job_status(db, job_id, "EXPORTING")
        time.sleep(3)  # Simulates connecting to GEE and initiating export task
        
        # Step 2: GEE Export complete
        update_job_status(db, job_id, "EXPORTED")
        time.sleep(2)  # Simulates GEE writing to Cloud/Local storage
        
        # Step 3: Ingestion / Download simulation
        update_job_status(db, job_id, "DOWNLOADED")
        time.sleep(2)  # Simulates scanning, copying, and cataloging local metadata
        
        # Step 4: AI Inference Pipeline simulation
        update_job_status(db, job_id, "ANALYZING")
        time.sleep(3)  # Simulates running forest cover, carbon, health assessment model stubs
        
        # Step 5: Terminal Completion
        update_job_status(db, job_id, "COMPLETED")
        logger.info("Async pipeline execution for Job %d finished successfully.", job_id)
        
    except Exception as exc:
        logger.exception("Async pipeline runner encountered a fatal exception on Job %d:", job_id)
        update_job_status(db, job_id, "FAILED", error_message=str(exc))
    finally:
        db.close()
