import logging
from app.db import SessionLocal
from app.models.report import Report
from app.services.report_generator import generate_full_report
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.report_tasks.run_report_generation_task")
def run_report_generation_task(job_id: int):
    """
    Celery task: Compiles executive PDF & HTML reports and saves database Report record.
    """
    logger.info("Starting Report Generation Task for Job ID: %d", job_id)
    db = SessionLocal()
    try:
        summary_text, html_path, pdf_path = generate_full_report(job_id, db)

        db_report = db.query(Report).filter(Report.job_id == job_id).first()
        if not db_report:
            db_report = Report(
                job_id=job_id,
                file_path=pdf_path
            )
            db.add(db_report)
        else:
            db_report.file_path = pdf_path

        db.commit()
        logger.info("Report Generation Task for Job ID %d completed. PDF: %s", job_id, pdf_path)

    except Exception as exc:
        logger.exception("Report Generation Task failed for Job ID %d:", job_id)
        raise exc
    finally:
        db.close()
