import os
import logging
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.job import Job
from app.models.aoi import AOI
from app.models.satellite_dataset import SatelliteDataset
from app.models.analysis_result import AnalysisResult
from app.services.ai_analysis_engine import analyze_geotiff
from app.services.job_orchestrator import update_job_status
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.analysis_tasks.run_ai_analysis_task")
def run_ai_analysis_task(job_id: int):
    """
    Celery task: Ingest 10-band GeoTIFF, run AI inference metrics, and persist AnalysisResult.
    """
    logger.info("Starting AI Analysis Task for Job ID: %d", job_id)
    db = SessionLocal()
    try:
        # 1. Update job status to ANALYZING
        update_job_status(db, job_id, "ANALYZING")

        # 2. Retrieve Job, AOI, and SatelliteDataset
        db_job = db.query(Job).filter(Job.id == job_id).first()
        if not db_job:
            raise ValueError(f"Job #{job_id} not found in database.")

        db_aoi = db.query(AOI).filter(AOI.id == db_job.aoi_id).first()
        if not db_aoi:
            raise ValueError(f"AOI #{db_job.aoi_id} associated with Job #{job_id} not found.")

        dataset = db.query(SatelliteDataset).filter(SatelliteDataset.job_id == job_id).first()
        if not dataset or not dataset.local_path or not os.path.exists(dataset.local_path):
            # Fallback path if local path record is missing
            geotiff_path = os.path.join("storage", "geotiffs", f"job_{job_id}.tif")
        else:
            geotiff_path = dataset.local_path

        # Calculate observation window length in days
        observation_days = (db_job.end_date - db_job.start_date).days if (db_job.end_date and db_job.start_date) else 30
        observation_days = max(1, observation_days)

        # 3. Run AI Inference Engine
        results = analyze_geotiff(
            geotiff_path=geotiff_path,
            area_hectares=float(db_aoi.area_hectares or 100.0),
            job_id=job_id,
            observation_days=observation_days
        )

        # 4. Save/Update AnalysisResult in Database
        analysis_record = db.query(AnalysisResult).filter(AnalysisResult.job_id == job_id).first()
        if not analysis_record:
            analysis_record = AnalysisResult(
                job_id=job_id,
                forest_cover_pct=results["forest_cover_pct"],
                tree_count=results["tree_count"],
                biomass_tons=results["biomass_tons"],
                carbon_tons=results["carbon_tons"],
                co2_equivalent_tons=results["co2_equivalent_tons"],
                health_index=results["health_index"],
                health_category=results["health_category"],
                suitability_score=results["suitability_score"],
                forest_loss_ha=results["forest_loss_ha"],
                forest_gain_ha=results["forest_gain_ha"],
                result_layers=results["result_layers"]
            )
            db.add(analysis_record)
        else:
            analysis_record.forest_cover_pct = results["forest_cover_pct"]
            analysis_record.tree_count = results["tree_count"]
            analysis_record.biomass_tons = results["biomass_tons"]
            analysis_record.carbon_tons = results["carbon_tons"]
            analysis_record.co2_equivalent_tons = results["co2_equivalent_tons"]
            analysis_record.health_index = results["health_index"]
            analysis_record.health_category = results["health_category"]
            analysis_record.suitability_score = results["suitability_score"]
            analysis_record.forest_loss_ha = results["forest_loss_ha"]
            analysis_record.forest_gain_ha = results["forest_gain_ha"]
            analysis_record.result_layers = results["result_layers"]

        db.commit()

        # 5. Transition status to COMPLETED
        update_job_status(db, job_id, "COMPLETED")
        logger.info("AI Analysis Task for Job ID %d completed successfully.", job_id)

    except Exception as exc:
        logger.exception("AI Analysis Task failed for Job ID %d:", job_id)
        update_job_status(db, job_id, "FAILED", error_message=str(exc))
        raise exc
    finally:
        db.close()
